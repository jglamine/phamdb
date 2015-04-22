Cdd/Cdd.rps: Cdd

Cdd: Cdd_LE.tar.gz
	mkdir Cdd
	tar -zxvf Cdd_LE.tar.gz -C Cdd

Cdd_LE.tar.gz:
	wget ftp://ftp.ncbi.nlm.nih.gov/pub/mmdb/cdd/little_endian/Cdd_LE.tar.gz

all: Cdd/Cdd.rps

clean:
	rm -rf Cdd
	rm -f Cdd_LE.tar.gz
