-- MySQL dump 10.13  Distrib 5.7.30, for Linux (x86_64)
--
-- Host: localhost    Database: Actinobacteriophage
-- ------------------------------------------------------
-- Server version	5.7.30-0ubuntu0.18.04.1

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

--
-- Table structure for table `domain`
--

DROP TABLE IF EXISTS `domain`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `domain` (
  `ID` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `HitID` varchar(25) NOT NULL,
  `Description` blob,
  `DomainID` varchar(10) DEFAULT NULL,
  `Name` varchar(25) DEFAULT NULL,
  PRIMARY KEY (`ID`),
  UNIQUE KEY `hit_id` (`HitID`)
) ENGINE=InnoDB AUTO_INCREMENT=3052009 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `domain`
--

LOCK TABLES `domain` WRITE;
/*!40000 ALTER TABLE `domain` DISABLE KEYS */;
/*!40000 ALTER TABLE `domain` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `gene`
--

DROP TABLE IF EXISTS `gene`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `gene` (
  `GeneID` varchar(35) NOT NULL DEFAULT '',
  `PhageID` varchar(25) NOT NULL,
  `Start` mediumint(9) NOT NULL,
  `Stop` mediumint(9) NOT NULL,
  `Length` mediumint(9) NOT NULL,
  `Name` varchar(50) NOT NULL,
  `Translation` blob,
  `Orientation` enum('F','R') DEFAULT NULL,
  `Notes` blob,
  `DomainStatus` tinyint(1) NOT NULL DEFAULT '0',
  `LocusTag` varchar(50) DEFAULT NULL,
  `Parts` tinyint(1) DEFAULT NULL,
  `PhamID` int(10) unsigned DEFAULT NULL,
  PRIMARY KEY (`GeneID`),
  KEY `PhageID` (`PhageID`),
  KEY `PhamID` (`PhamID`),
  CONSTRAINT `gene_ibfk_2` FOREIGN KEY (`PhageID`) REFERENCES `phage` (`PhageID`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `gene_ibfk_3` FOREIGN KEY (`PhamID`) REFERENCES `pham` (`PhamID`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `gene`
--

LOCK TABLES `gene` WRITE;
/*!40000 ALTER TABLE `gene` DISABLE KEYS */;
/*!40000 ALTER TABLE `gene` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `gene_domain`
--

DROP TABLE IF EXISTS `gene_domain`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `gene_domain` (
  `ID` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `GeneID` varchar(35) DEFAULT NULL,
  `HitID` varchar(25) NOT NULL,
  `QueryStart` int(10) unsigned NOT NULL,
  `QueryEnd` int(10) unsigned NOT NULL,
  `Expect` double unsigned NOT NULL,
  PRIMARY KEY (`ID`),
  UNIQUE KEY `GeneID__hit_id` (`GeneID`,`HitID`),
  KEY `hit_id` (`HitID`),
  CONSTRAINT `gene_domain_ibfk_1` FOREIGN KEY (`GeneID`) REFERENCES `gene` (`GeneID`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `gene_domain_ibfk_2` FOREIGN KEY (`HitID`) REFERENCES `domain` (`HitID`)
) ENGINE=InnoDB AUTO_INCREMENT=448806 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `gene_domain`
--

LOCK TABLES `gene_domain` WRITE;
/*!40000 ALTER TABLE `gene_domain` DISABLE KEYS */;
/*!40000 ALTER TABLE `gene_domain` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `phage`
--

DROP TABLE IF EXISTS `phage`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `phage` (
  `PhageID` varchar(25) NOT NULL,
  `Accession` varchar(15) NOT NULL,
  `Name` varchar(50) NOT NULL,
  `HostGenus` varchar(50) DEFAULT NULL,
  `Sequence` mediumblob NOT NULL,
  `Length` mediumint(9) NOT NULL,
  `DateLastModified` datetime DEFAULT NULL,
  `Notes` blob,
  `GC` float DEFAULT NULL,
  `Status` enum('unknown','draft','final') DEFAULT NULL,
  `RetrieveRecord` tinyint(1) NOT NULL DEFAULT '0',
  `AnnotationAuthor` tinyint(1) NOT NULL DEFAULT '0',
  `Cluster` varchar(5) DEFAULT NULL,
  `Subcluster` varchar(5) DEFAULT NULL,
  PRIMARY KEY (`PhageID`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `phage`
--

LOCK TABLES `phage` WRITE;
/*!40000 ALTER TABLE `phage` DISABLE KEYS */;
/*!40000 ALTER TABLE `phage` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `pham`
--

DROP TABLE IF EXISTS `pham`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `pham` (
  `PhamID` int(10) unsigned NOT NULL,
  `Color` char(7) NOT NULL,
  PRIMARY KEY (`PhamID`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `pham`
--

LOCK TABLES `pham` WRITE;
/*!40000 ALTER TABLE `pham` DISABLE KEYS */;
/*!40000 ALTER TABLE `pham` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tmrna`
--

DROP TABLE IF EXISTS `tmrna`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tmrna` (
  `GeneID` varchar(35) NOT NULL,
  `PhageID` varchar(25) NOT NULL,
  `Start` mediumint(9) NOT NULL,
  `Stop` mediumint(9) NOT NULL,
  `Length` mediumint(9) NOT NULL,
  `Name` varchar(50) NOT NULL,
  `Orientation` enum('F','R') NOT NULL,
  `Note` blob,
  `LocusTag` varchar(35) DEFAULT NULL,
  `PeptideTag` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`GeneID`),
  KEY `PhageID` (`PhageID`),
  CONSTRAINT `tmrna_ibfk_1` FOREIGN KEY (`PhageID`) REFERENCES `phage` (`PhageID`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tmrna`
--

LOCK TABLES `tmrna` WRITE;
/*!40000 ALTER TABLE `tmrna` DISABLE KEYS */;
/*!40000 ALTER TABLE `tmrna` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `trna`
--

DROP TABLE IF EXISTS `trna`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `trna` (
  `GeneID` varchar(35) NOT NULL,
  `PhageID` varchar(25) NOT NULL,
  `Start` mediumint(9) NOT NULL,
  `Stop` mediumint(9) NOT NULL,
  `Length` mediumint(9) NOT NULL,
  `Name` varchar(50) NOT NULL,
  `Orientation` enum('F','R') NOT NULL,
  `Note` blob,
  `LocusTag` varchar(35) DEFAULT NULL,
  `AminoAcid` enum('Ala','Arg','Asn','Asp','Cys','fMet','Gln','Glu','Gly','His','Ile','Ile2','Leu','Lys','Met','Phe','Pro','Pyl','SeC','Ser','Thr','Trp','Tyr','Val','Stop','OTHER') NOT NULL,
  `Anticodon` varchar(4) NOT NULL,
  `Structure` blob,
  `Source` enum('aragorn','trnascan','both') DEFAULT NULL,
  PRIMARY KEY (`GeneID`),
  KEY `PhageID` (`PhageID`),
  CONSTRAINT `trna_ibfk_1` FOREIGN KEY (`PhageID`) REFERENCES `phage` (`PhageID`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `trna`
--

LOCK TABLES `trna` WRITE;
/*!40000 ALTER TABLE `trna` DISABLE KEYS */;
/*!40000 ALTER TABLE `trna` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `version`
--

DROP TABLE IF EXISTS `version`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `version` (
  `Version` int(11) unsigned NOT NULL,
  `SchemaVersion` int(11) unsigned NOT NULL,
  PRIMARY KEY (`Version`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `version`
--

LOCK TABLES `version` WRITE;
/*!40000 ALTER TABLE `version` DISABLE KEYS */;
INSERT INTO `version` VALUES (0,10);
/*!40000 ALTER TABLE `version` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2020-07-10  9:41:46
