import tempfile
import os
import os.path
import shutil
from itertools import izip
import subprocess32

_DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')

def _default_callback(*args, **kwargs):
    pass

def cluster(gene_sequences, gene_ids, on_first_iteration_done=_default_callback):
    """Group genes into clusters (phams) by similarity.

    Returns a dictionary mapping pham id to a list of gene ids in that pham.


    gene_sequences: a list of gene sequences (strings) to cluster.
    gene_ids: a list of gene ids corresponding to the sequences.
        gene_ids[i] is the id for the sequence in gene_sequences[i]
    on_first_iteration_done: a callback function used to report status.

    Exceptions: MemoryError - Occurs when the system does not have enough
    memory to run kclust.
    """
    kclust = _KClust(on_first_iteration_done)
    return kclust.cluster(gene_sequences, gene_ids)

class _KClust(object):
    def __init__(self, on_first_iteration_done):
        self.on_first_iteration_done = on_first_iteration_done
        self._gene_id_to_sequence = {}

    def cluster(self, gene_sequences, gene_ids):
        """
        Exceptions: MemoryError
        """
        self._gene_id_to_sequence = {}
        for gene_id, sequence in izip(gene_ids, gene_sequences):
            self._gene_id_to_sequence[gene_id] = sequence

        # build kclust query file
        # run first kclust iteration
        try:
            first_iteration = self._first_iteration(gene_ids)
        except subprocess32.CalledProcessError as err:
            if err.returncode == -9:
                # the process ran out of memory
                raise MemoryError(err)
            else:
                raise

        self.on_first_iteration_done()

        # run second kClust iteration
        try:
            second_iteration = self._second_iteration(first_iteration)
        except subprocess32.CalledProcessError as err:
            if err.returncode == -9:
                # the process ran out of memory
                raise MemoryError
            else:
                raise

        # combine iterations
        phams = self._combine_iterations(gene_ids, first_iteration, second_iteration)

        return phams.pham_id_to_gene_ids

    def _first_iteration(self, gene_ids):
        """Executes the first kClust iteration.

        Returns a _Phams object.
        """
        try:
            fasta_filename = None
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as fasta_file:
                fasta_filename = fasta_file.name
                for gene_id in gene_ids:
                    sequence = self._gene_id_to_sequence[gene_id]
                    _write_fasta_record(fasta_file, sequence, gene_id)
            
            return self._run_kclust(fasta_filename, 3.53, 0.25)

        finally:
            if fasta_filename is not None:
                try:
                    os.remove(fasta_filename)
                except IOError:
                    pass

    def _run_kclust(self, fasta_input_filename, s, c):
        # run kclust
        output_directory = tempfile.mkdtemp(suffix='kclust')
        try:
            kclust_path = os.path.join(_DATA_DIR, 'kclust', 'kClust')
            command = '{} -i {} -d {} -s {} -c {}'.format(kclust_path, fasta_input_filename, output_directory, s, c)
            _call(command)

            # read results
            return self._read_kclust_results(output_directory)

        finally:
            shutil.rmtree(output_directory)

    def _read_kclust_results(self, kclust_directory):
        """Reads results from output files created by kclust.

        Returns a _Phams object.

        kClust produces the following files as output:
        db_sorted.fas       : The input database sorted by sequence length.
        headers.dmp         : The mapping sequence index -> sequence header.
        representatives.fas : All representative sequences.
        clusters.dmp        : Mapping sequence index -> index of the
                              representative sequence of its cluster.
                              Each representative sequence in a cluster is
                              therefore mapped to itself.
        """
        index_to_gene_id = {}
        phams = _Phams()

        with open(os.path.join(kclust_directory, 'headers.dmp')) as headers:
            for line in headers:
                line = line.split()
                index = line[0]
                gene_id = line[1][1:] # remove the leading '>' character
                index_to_gene_id[index] = gene_id

        with open(os.path.join(kclust_directory, 'clusters.dmp')) as clusters:
            for line_number, line in enumerate(clusters):
                if line_number == 0:
                    continue

                index, pham_id = line.split()
                pham_id = int(pham_id)
                gene_id = index_to_gene_id[index]
                phams.insert(gene_id, pham_id)

        return phams

    def _second_iteration(self, phams):
        """Run the second kClust iteration.

        Phams from the first iteration are each mapped to a single consensus sequence.
        kClust is run on these consensus sequences,
        creating groups of consensus sequences.
        """
        # create fasta file
        try:
            fasta_filename = None

            # build the fasta query file to be used with kClust
            # the file is built by finding consensus sequences for each pham
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as fasta_file:
                fasta_filename = fasta_file.name
                for pham_id, gene_ids in phams.pham_id_to_gene_ids.iteritems():
                    if len(gene_ids) == 1:
                        # phams with just one gene can be written directly
                        gene_id = gene_ids[0]
                        sequence = self._gene_id_to_sequence[gene_id]
                        _write_fasta_record(fasta_file, sequence, pham_id)
                    elif len(gene_ids) > 1:
                        # phams with more than one gene need a consensus sequence
                        sequence = self._consensus(gene_ids)
                        _write_fasta_record(fasta_file, sequence, pham_id)
            
            # run the final kClust iteration
            second_phams = self._run_kclust(fasta_filename, 0, 0.5)
            return second_phams

        finally:
            if fasta_filename is not None:
                try:
                    os.remove(fasta_filename)
                except IOError:
                    pass

    def _consensus(self, gene_ids):
        output_directory = tempfile.mkdtemp(suffix='-hh')
        try:
            # create fasta file for all genes in the pham
            with tempfile.NamedTemporaryFile(mode='w', delete=False, dir=output_directory) as fasta_file:
                fasta_filename = fasta_file.name
                for gene_id in gene_ids:
                    sequence = self._gene_id_to_sequence[gene_id]
                    _write_fasta_record(fasta_file, sequence, gene_id)

            # compute alignment
            output_filename = os.path.join(output_directory, 'alignment.fasta')
            _call('kalign -i {} -o {} -q'.format(fasta_filename, output_filename))
            hmm_filename = os.path.join(output_directory, 'alignment.hmm')
            _call('hhmake -i {} -o {}'.format(output_filename, hmm_filename))
            consensus_filename = os.path.join(output_directory, 'consensus.a3m')
            _call('hhconsensus -v 0 -i {} -o {}'.format(hmm_filename, consensus_filename))

            # read consensus the sequence from the 3rd line of the output file
            consensus_sequence = None
            with open(consensus_filename, 'r') as consensus_file:
                for line_number, line in enumerate(consensus_file):
                    if line_number == 2:
                        consensus_sequence = line
                        break

            if consensus_sequence is None:
                raise RuntimeError('Unable to read consensus sequence: file `{}` is too short.'.format(consensus_filename))

            return consensus_sequence
        finally:
            shutil.rmtree(output_directory)

    def _combine_iterations(self, gene_ids, first_iteration, second_iteration):
        phams = _Phams()
        for gene_id in gene_ids:
            first_pham_id = first_iteration.gene_id_to_pham_id[gene_id]
            final_pham_id = second_iteration.gene_id_to_pham_id[str(first_pham_id)]
            phams.insert(gene_id, final_pham_id)
        return phams

class _Phams(object):
    def __init__(self):
        self.pham_id_to_gene_ids = {}
        self.gene_id_to_pham_id = {}

    def insert(self, gene_id, pham_id):
        self.gene_id_to_pham_id[gene_id] = pham_id
        if pham_id not in self.pham_id_to_gene_ids:
            self.pham_id_to_gene_ids[pham_id] = []
        self.pham_id_to_gene_ids[pham_id].append(gene_id)

def _write_fasta_record(fasta_file, sequence, gene_id):
    sequence = sequence.replace('-', 'M')
    fasta_file.write('>{}\n'.format(gene_id))
    index = 0
    while index < len(sequence):
        fasta_file.write('{}\n'.format(sequence[index:index + 80]))
        index += 80

def _call(command):
    args = command.split()
    with open(os.devnull, 'wb') as DEVNULL:
        code = subprocess32.check_call(args, stdout=DEVNULL, stderr=DEVNULL)
    return code