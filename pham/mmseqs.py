import os
import os.path
import shutil
import subprocess as sp
import shlex

_DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')


def _default_callback(*args, **kwargs):
    pass


def cluster(gene_sequences, gene_ids,
            on_first_iteration_done=_default_callback):
    """
    Group genes into clusters (phams) by similarity.

    Returns a dictionary mapping pham id to a list of gene ids in that pham.

    gene_sequences: a list of gene sequences (strings) to cluster.
    gene_ids: a list of gene ids corresponding to the sequences.
        gene_ids[i] is the id for the sequence in gene_sequences[i]
    on_first_iteration_done: a callback function used to report status.

    Exceptions: MemoryError - Occurs when the system does not have enough
    memory to run MMseqs2.
    """
    mmseqs = _MMseqs(on_first_iteration_done)
    return mmseqs.cluster(gene_sequences, gene_ids)


class _MMseqs(object):
    def __init__(self, on_first_iteration_done):
        self.on_first_iteration_done = on_first_iteration_done
        self._gene_id_to_sequence = {}
        self._mmseqs_path = os.path.join(_DATA_DIR, "mmseqs/bin", "mmseqs")
        self._working_dir = "/tmp/mmseqs"
        self._fasta = os.path.join(self._working_dir, "input.fasta")
        self._seq_db = os.path.join(self._working_dir, "sequenceDB")
        self._clu_db = os.path.join(self._working_dir, "clusterDB")
        self._fiseq_db = os.path.join(self._working_dir, "first_seqfileDB")
        self._fiout = os.path.join(self._working_dir, "first_iter_out.fasta")
        self._pro_db = os.path.join(self._working_dir, "profileDB")
        self._con_db = os.path.join(self._working_dir, "consensusDB")
        self._aln_db = os.path.join(self._working_dir, "alignDB")
        self._res_db = os.path.join(self._working_dir, "resultDB")
        self._siseq_db = os.path.join(self._working_dir, "second_seqfileDB")
        self._siout = os.path.join(self._working_dir, "second_iter_out.fasta")

    def cluster(self, gene_sequences, gene_ids):
        """
        Main workflow method for _MMseqs object - directs the flow of
        information between _MMseqs methods to cluster the input
        sequences.

        gene_ids[i] is assumed to be the id for gene_sequences[i]

        :param gene_sequences: gene sequences (strings) to cluster
        :type gene_sequences: list
        :param gene_ids: gene ids corresponding to the sequences
        :type gene_ids: list
        :return: phams.pham_ids_to_gene_ids
        :rtype: dict

        :raise: MemoryError
        """
        # Do setup steps - map gene ids to sequences and create
        # temporary directory for file I/O
        self._gene_id_to_sequence = dict()
        for gene_id, sequence in zip(gene_ids, gene_sequences):
            self._gene_id_to_sequence[gene_id] = sequence

        _refresh_dir(self._working_dir)

        # Build MMseqs query file and run first MMseqs2 iteration
        try:
            first_iteration = self._first_iteration(gene_ids)
        except sp.CalledProcessError as err:
            if err.returncode == -9:
                raise MemoryError(err)
            else:
                raise

        self.on_first_iteration_done()

        # Run second MMseqs2 iteration
        try:
            second_iteration = self._second_iteration()
        except sp.CalledProcessError as err:
            if err.returncode == -9:
                raise MemoryError(err)
            else:
                raise

        # combine iterations
        phams = self._combine_iterations(first_iteration, second_iteration)

        return phams.pham_id_to_gene_ids

    def _first_iteration(self, gene_ids):
        """
        Performs the first iteration of MMseqs2 clustering
        :param gene_ids:
        :return: phams
        :rtype: _Phams
        """
        # Shortcuts for filenames:
        fasta = self._fasta
        seqdb = self._seq_db
        cludb = self._clu_db
        fiseq = self._fiseq_db
        fiout = self._fiout

        # Write fasta input
        with open(fasta, "w") as fh:
            for gene_id in gene_ids:
                sequence = self._gene_id_to_sequence[gene_id].decode("utf-8")
                _write_fasta_record(fh, sequence, gene_id)

        # Create MMseqs2 database from fasta
        command = f"{self._mmseqs_path} createdb {fasta} {seqdb} -v 0"
        _call(command)

        # Perform first iteration of clustering
        command = f"{self._mmseqs_path} cluster {seqdb} {cludb} " \
                  f"{self._working_dir} -v 0 --min-seq-id 0.45 -c 0.75 " \
                  f"-e 0.001 -s 8 --max-seqs 1000 --cluster-steps 1 " \
                  f"--alignment-mode 3 --cov-mode 0 --cluster-mode 0"
        _call(command)

        # Parse and store first-iteration phams
        command = f"{self._mmseqs_path} createseqfiledb {seqdb} {cludb} " \
                  f"{fiseq} -v 0"
        _call(command)

        command = f"{self._mmseqs_path} result2flat {seqdb} {seqdb} " \
                  f"{fiseq} {fiout} -v 0"
        _call(command)

        return self._read_mmseqs_result(fiout)

    def _second_iteration(self):
        """
        Run the second MMseqs2 iteration.

        :return: phams
        :rtype: _Phams
        """
        # Shortcuts for filenames:
        seqdb = self._seq_db
        cludb = self._clu_db
        prodb = self._pro_db
        condb = self._con_db
        alndb = self._aln_db
        # resdb = self._res_db
        siseq = self._siseq_db
        siout = self._siout

        # Build MMseqs2 profile database
        command = f"{self._mmseqs_path} result2profile {seqdb} {seqdb} " \
                  f"{cludb} {prodb} -v 0"
        _call(command)

        # Build MMseqs2 profile consensus database
        command = f"{self._mmseqs_path} profile2consensus {prodb} {condb} -v 0"
        _call(command)

        # Search the profiles against their consensuses
        command = f"{self._mmseqs_path} search {prodb} {condb} {alndb} " \
                  f"{self._working_dir} --min-seq-id 0.30 -c 0.50 " \
                  f"--e-profile 0.001 --add-self-matches 1 -v 0"
        _call(command)

        # Cluster the profile/consensus alignment results
        command = f"{self._mmseqs_path} clust {condb} {alndb} {cludb} -v 0"
        _call(command)

        # Parse and store second-iteration phams
        # command = f"{self._mmseqs_path} createseqfiledb {seqdb} {resdb} " \
        command = f"{self._mmseqs_path} createseqfiledb {seqdb} {cludb} " \
                  f"{siseq} -v 0"
        _call(command)

        command = f"{self._mmseqs_path} result2flat {prodb} {condb} " \
                  f"{siseq} {siout} -v 0"
        _call(command)

        return self._read_mmseqs_result(siout)

    @staticmethod
    def _read_mmseqs_result(filename):
        """
        Parses the MMseqs2 FASTA-like file into a _Phams object.

        :param filename: path to the file to parse
        :return: ps
        :rtype: _Phams
        """
        phams = dict()
        gene_ids = list()
        pham_id = 0

        with open(filename, "r") as fh:
            prior = fh.readline()
            current = fh.readline()

            # Iterate until EOF
            while current:
                # If current is a header
                if current.startswith(">"):
                    # If prior was also a header, dump the current pham
                    # and start new
                    if prior.startswith(">"):
                        try:
                            gene_ids.pop(-1)
                        except IndexError:
                            # This will happen for the first pham...
                            pass
                        phams[pham_id] = gene_ids
                        pham_id += 1
                        gene_ids = [current.lstrip(">").rstrip()]
                    # Otherwise keep adding to current pham
                    else:
                        gene_ids.append(current.lstrip(">").rstrip())
                # If current is a translation, do nothing
                else:
                    pass
                # Next!
                prior, current = current, fh.readline()
            # Dump last pham, and pop placeholder
            phams[pham_id] = gene_ids
            phams.pop(0)

        ps = _Phams()
        for pham_id, gene_ids in phams.items():
            for gene_id in gene_ids:
                ps.insert(gene_id, pham_id)

        return ps

    @staticmethod
    def _combine_iterations(first_iteration, second_iteration):
        """
        Combine two MMseqs2 iterations into a single _Pham object.

        Keeps the pham ids from the second iteration.

        :param first_iteration: pham mappings from first iteration
        :type first_iteration: _Phams
        :param second_iteration: pham mappings from second iteration
        :type second_iteration: _Phams
        :return: phams
        :rtype: _Phams
        """
        phams = _Phams()
        for pham_id, gene_ids in second_iteration.pham_id_to_gene_ids.items():
            for gene_id in gene_ids:
                old_pham_id = first_iteration.gene_id_to_pham_id[gene_id]
                old_pham = first_iteration.pham_id_to_gene_ids[old_pham_id]
                for gene in old_pham:
                    phams.insert(gene, pham_id)
        return phams


class _Phams(object):
    """Object used to hold phams.

    Maintains two maps: pham_id_to_gene_ids, and gene_id_to_pham_id.
    """

    def __init__(self):
        self.pham_id_to_gene_ids = {}
        self.gene_id_to_pham_id = {}

    def insert(self, gene_id, pham_id):
        self.gene_id_to_pham_id[gene_id] = pham_id
        if pham_id not in self.pham_id_to_gene_ids:
            self.pham_id_to_gene_ids[pham_id] = []
        self.pham_id_to_gene_ids[pham_id].append(gene_id)


def _refresh_dir(directory):
    """
    If the input directory already exists, recursively removes it.
    Then creates a new copy of the input directory.
    :param directory: the path to the directory to refresh
    """
    if os.path.exists(directory):
        shutil.rmtree(directory)
    os.makedirs(directory)


def _write_fasta_record(fasta_file, sequence, gene_id):
    """
    Saves a gene sequence as a fasta file.
    """
    sequence = sequence.replace('-', 'M')
    fasta_file.write('>{}\n'.format(gene_id))
    index = 0
    while index < len(sequence):
        fasta_file.write('{}\n'.format(sequence[index:index + 80]))
        index += 80


def _call(command):
    """
    Wrapper to call a shell command, discarding all output
    printed to the screen.

    Returns the exit code of the command.
    """
    args = shlex.split(command)
    code = sp.check_call(args, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return code
