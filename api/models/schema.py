"""Modeles SQLAlchemy reflechissant les tables ecrites par etl/clean_and_load.py."""
from geoalchemy2 import Geometry
from sqlalchemy import Column, Float, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Region(Base):
    __tablename__ = "regions"

    id = Column(String, primary_key=True)
    nom = Column(String)
    superficie_km2 = Column(Float)
    geometry = Column(Geometry(geometry_type="MULTIPOLYGON", srid=4326))


class Gare(Base):
    __tablename__ = "gares"

    id = Column(String, primary_key=True)
    nom = Column(String)
    ville = Column(String)
    source = Column(String)
    region_id = Column(String)
    osm_id = Column(String)
    osm_nom = Column(String)
    distance_osm_m = Column(Float)
    appariement_osm = Column(String)
    geometry = Column(Geometry(geometry_type="POINT", srid=4326))


class Ligne(Base):
    __tablename__ = "lignes"

    id = Column(String, primary_key=True)
    nom = Column(String)
    type_ligne = Column(String)
    longueur_km = Column(Float)
    geometry = Column(Geometry(geometry_type="GEOMETRY", srid=4326))


class VoieOsm(Base):
    __tablename__ = "voies_osm"

    id = Column(String, primary_key=True)
    geometry = Column(Geometry(geometry_type="LINESTRING", srid=4326))


class Horaire(Base):
    __tablename__ = "horaires"

    id = Column(Integer, primary_key=True)
    trip_id = Column(String)
    gare_id = Column(String)
    ligne_id = Column(String)
    heure_arrivee = Column(String)
    heure_depart = Column(String)
    stop_sequence = Column(Integer)
    sens = Column(String)
    jours = Column(String)
