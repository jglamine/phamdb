/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;

DROP TABLE IF EXISTS `domain`;
DROP TABLE IF EXISTS `gene`;
DROP TABLE IF EXISTS `gene_domain`;
DROP TABLE IF EXISTS `node`;
DROP TABLE IF EXISTS `phage`;
DROP TABLE IF EXISTS `pham`;
DROP TABLE IF EXISTS `pham_color`;
DROP TABLE IF EXISTS `pham_history`;
DROP TABLE IF EXISTS `pham_old`;
DROP TABLE IF EXISTS `scores_summary`;
DROP TABLE IF EXISTS `version`;

CREATE TABLE `domain` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `hit_id` varchar(127) NOT NULL,
  `description` blob,
  `DomainID` varchar(10) DEFAULT NULL,
  `Name` varchar(127) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `hit_id` (`hit_id`)
) DEFAULT CHARSET=latin1;

CREATE TABLE `gene` (
  `GeneID` varchar(127) NOT NULL,
  `PhageID` varchar(127) NOT NULL,
  `Start` int NOT NULL,
  `Stop` int NOT NULL,
  `Length` int NOT NULL,
  `Name` varchar(127) NOT NULL,
  `TypeID` varchar(10) DEFAULT NULL,
  `translation` varchar(10000) DEFAULT NULL,
  `StartCodon` enum('ATG','GTG','TTG') DEFAULT NULL,
  `StopCodon` enum('TAA','TAG','TGA') DEFAULT NULL,
  `Orientation` enum('F','R') DEFAULT NULL,
  `GC1` float DEFAULT NULL,
  `GC2` float DEFAULT NULL,
  `GC3` float DEFAULT NULL,
  `GC` float DEFAULT NULL,
  `LeftNeighbor` varchar(127) DEFAULT NULL,
  `RightNeighbor` varchar(127) DEFAULT NULL,
  `Notes` blob,
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `clustalw_status` enum('avail','pending','stale','done') NOT NULL DEFAULT 'avail',
  `blast_status` enum('avail','pending','stale','done') NOT NULL DEFAULT 'avail',
  `cdd_status` TINYINT NOT NULL DEFAULT '0',
  PRIMARY KEY (`GeneID`),
  KEY `PhageID` (`PhageID`),
  KEY `id` (`id`),
  CONSTRAINT `gene_ibfk_1` FOREIGN KEY (`PhageID`) REFERENCES `phage` (`PhageID`) ON UPDATE CASCADE ON DELETE CASCADE
) DEFAULT CHARSET=latin1;

CREATE TABLE `gene_domain` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `GeneID` varchar(127) NOT NULL,
  `hit_id` varchar(127) NOT NULL,
  `query_start` int unsigned NOT NULL,
  `query_end` int unsigned NOT NULL,
  `expect` double unsigned NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `GeneID__hit_id` (`GeneID`,`hit_id`),
  KEY `hit_id` (`hit_id`),
  CONSTRAINT `gene_domain_ibfk_1` FOREIGN KEY (`GeneID`) REFERENCES `gene` (`GeneID`) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT `gene_domain_ibfk_2` FOREIGN KEY (`hit_id`) REFERENCES `domain` (`hit_id`) ON UPDATE CASCADE ON DELETE CASCADE
) DEFAULT CHARSET=latin1;

CREATE TABLE `node` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `platform` varchar(15) DEFAULT NULL,
  `hostname` varchar(127) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `hostname_index` (`hostname`)
) DEFAULT CHARSET=latin1;

CREATE TABLE `phage` (
  `PhageID` varchar(127) NOT NULL,
  `Accession` varchar(15) NOT NULL,
  `Name` varchar(127) NOT NULL,
  `Isolated` varchar(127) DEFAULT NULL,
  `HostStrain` varchar(127) DEFAULT NULL,
  `Sequence` mediumblob NOT NULL,
  `SequenceLength` int NOT NULL,
  `Prophage` enum('yes','no') DEFAULT NULL,
  `ProphageOffset` int DEFAULT NULL,
  `DateLastModified` datetime DEFAULT NULL,
  `DateLastSearched` datetime DEFAULT NULL,
  `Notes` blob,
  `GC` float NOT NULL,
  `Cluster` varchar(5) DEFAULT NULL,
  PRIMARY KEY (`PhageID`)
) DEFAULT CHARSET=latin1;

CREATE TABLE `pham` (
  `GeneID` varchar(127) NOT NULL,
  `name` int unsigned DEFAULT NULL,
  `orderAdded` int unsigned NOT NULL AUTO_INCREMENT,
  PRIMARY KEY (`GeneID`),
  KEY `orderAdded_index` (`orderAdded`),
  KEY `name_index` (`name`),
  CONSTRAINT `pham_ibfk_1` FOREIGN KEY (`GeneID`) REFERENCES `gene` (`GeneID`) ON UPDATE CASCADE ON DELETE CASCADE
) DEFAULT CHARSET=latin1;

CREATE TABLE `pham_color` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `name` int unsigned NOT NULL,
  `color` char(7) NOT NULL,
  PRIMARY KEY (`id`)
) DEFAULT CHARSET=latin1;

CREATE TABLE `scores_summary` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `query` varchar(127) NOT NULL,
  `subject` varchar(127) NOT NULL,
  `blast_score` double unsigned DEFAULT NULL,
  `blast_bit_score` double unsigned DEFAULT NULL,
  `clustalw_score` decimal(5,4) unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `scores_summary_ibfk_1` (`query`),
  KEY `scores_summary_ibfk_2` (`subject`),
  CONSTRAINT `scores_summary_ibfk_1` FOREIGN KEY (`query`) REFERENCES `gene` (`GeneID`) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT `scores_summary_ibfk_2` FOREIGN KEY (`subject`) REFERENCES `gene` (`GeneID`) ON UPDATE CASCADE ON DELETE CASCADE
) DEFAULT CHARSET=latin1;

CREATE TABLE `version` (
  `id` int NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `version` int NOT NULL
);

INSERT INTO version (version)
VALUES (0);

/*!40101 SET character_set_client = @saved_cs_client */;

/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;
