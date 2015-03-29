
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
DROP TABLE IF EXISTS `domain`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `domain` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `hit_id` varchar(25) NOT NULL,
  `description` blob,
  `DomainID` varchar(10) DEFAULT NULL,
  `Name` varchar(25) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `hit_id` (`hit_id`)
) ENGINE=InnoDB AUTO_INCREMENT=53419 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `gene`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `gene` (
  `GeneID` varchar(30) NOT NULL,
  `PhageID` varchar(25) NOT NULL,
  `Start` mediumint(9) NOT NULL,
  `Stop` mediumint(9) NOT NULL,
  `Length` mediumint(9) NOT NULL,
  `Name` varchar(50) NOT NULL,
  `TypeID` varchar(10) DEFAULT NULL,
  `translation` varchar(10000) DEFAULT NULL,
  `StartCodon` enum('ATG','GTG','TTG') DEFAULT NULL,
  `StopCodon` enum('TAA','TAG','TGA') DEFAULT NULL,
  `Orientation` enum('F','R') DEFAULT NULL,
  `GC1` float DEFAULT NULL,
  `GC2` float DEFAULT NULL,
  `GC3` float DEFAULT NULL,
  `GC` float DEFAULT NULL,
  `LeftNeighbor` varchar(25) DEFAULT NULL,
  `RightNeighbor` varchar(25) DEFAULT NULL,
  `Notes` blob,
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `clustalw_status` enum('avail','pending','stale','done') NOT NULL DEFAULT 'avail',
  `blast_status` enum('avail','pending','stale','done') NOT NULL DEFAULT 'avail',
  PRIMARY KEY (`GeneID`),
  KEY `PhageID` (`PhageID`),
  KEY `id` (`id`),
  CONSTRAINT `gene_ibfk_1` FOREIGN KEY (`PhageID`) REFERENCES `phage` (`PhageID`) ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=12991 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `gene_domain`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `gene_domain` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `GeneID` varchar(30) NOT NULL,
  `hit_id` varchar(25) NOT NULL,
  `query_start` int(10) unsigned NOT NULL,
  `query_end` int(10) unsigned NOT NULL,
  `expect` double unsigned NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `GeneID__hit_id` (`GeneID`,`hit_id`),
  KEY `hit_id` (`hit_id`),
  CONSTRAINT `gene_domain_ibfk_1` FOREIGN KEY (`GeneID`) REFERENCES `gene` (`GeneID`) ON UPDATE CASCADE,
  CONSTRAINT `gene_domain_ibfk_2` FOREIGN KEY (`hit_id`) REFERENCES `domain` (`hit_id`)
) ENGINE=InnoDB AUTO_INCREMENT=99894 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `node`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `node` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `platform` varchar(15) DEFAULT NULL,
  `hostname` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `hostname_index` (`hostname`)
) ENGINE=InnoDB AUTO_INCREMENT=21 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `phage`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `phage` (
  `PhageID` varchar(25) NOT NULL,
  `Accession` varchar(15) NOT NULL,
  `Name` varchar(50) NOT NULL,
  `Isolated` varchar(100) DEFAULT NULL,
  `HostStrain` varchar(50) DEFAULT NULL,
  `Sequence` mediumblob NOT NULL,
  `SequenceLength` mediumint(9) NOT NULL,
  `Prophage` enum('yes','no') DEFAULT NULL,
  `ProphageOffset` int(11) DEFAULT NULL,
  `DateLastModified` datetime DEFAULT NULL,
  `DateLastSearched` datetime DEFAULT NULL,
  `Notes` blob,
  `GC` float NOT NULL,
  `Cluster` varchar(5) DEFAULT NULL,
  PRIMARY KEY (`PhageID`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `pham`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `pham` (
  `GeneID` varchar(30) NOT NULL,
  `name` int(10) unsigned DEFAULT NULL,
  `orderAdded` int(5) unsigned NOT NULL AUTO_INCREMENT,
  PRIMARY KEY (`GeneID`),
  KEY `orderAdded_index` (`orderAdded`),
  KEY `name_index` (`name`),
  CONSTRAINT `pham_ibfk_2` FOREIGN KEY (`GeneID`) REFERENCES `gene` (`GeneID`) ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=28182 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `pham_color`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `pham_color` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `name` int(10) unsigned NOT NULL,
  `color` char(7) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3543 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `pham_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `pham_history` (
  `name` int(10) unsigned NOT NULL,
  `parent` int(10) unsigned NOT NULL,
  `action` enum('join','split') NOT NULL,
  `datetime` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`name`,`parent`,`action`),
  KEY `parent_index` (`parent`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `pham_old`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `pham_old` (
  `GeneID` varchar(30) NOT NULL,
  `name` int(10) unsigned DEFAULT NULL,
  `orderAdded` int(5) unsigned NOT NULL AUTO_INCREMENT,
  PRIMARY KEY (`orderAdded`),
  KEY `orderAdded_index` (`orderAdded`),
  KEY `GeneID_index` (`GeneID`),
  CONSTRAINT `pham_old_ibfk_2` FOREIGN KEY (`GeneID`) REFERENCES `gene` (`GeneID`) ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=11826 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `scores_summary`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `scores_summary` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `query` varchar(30) NOT NULL,
  `subject` varchar(30) NOT NULL,
  `blast_score` double unsigned DEFAULT NULL,
  `blast_bit_score` double unsigned DEFAULT NULL,
  `clustalw_score` decimal(5,4) unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `scores_summary_ibfk_1` (`query`),
  KEY `scores_summary_ibfk_2` (`subject`),
  CONSTRAINT `scores_summary_ibfk_1` FOREIGN KEY (`query`) REFERENCES `gene` (`GeneID`) ON UPDATE CASCADE,
  CONSTRAINT `scores_summary_ibfk_2` FOREIGN KEY (`subject`) REFERENCES `gene` (`GeneID`) ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1526038 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

