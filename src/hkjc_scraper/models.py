"""
SQLAlchemy ORM models for HKJC racing database
香港賽馬會賽事資料庫 ORM 模型
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BIGINT,
    DATE,
    DECIMAL,
    INT,
    TEXT,
    VARCHAR,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all ORM models"""
    pass


# ============================================================================
# 賽日與賽事 (Meetings and Races)
# ============================================================================

class Meeting(Base):
    __tablename__ = "meeting"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(DATE, nullable=False)
    venue_code: Mapped[str] = mapped_column(VARCHAR(4), nullable=False)  # ST/HV
    venue_name: Mapped[Optional[str]] = mapped_column(VARCHAR(32))
    source_url: Mapped[Optional[str]] = mapped_column(TEXT)
    season: Mapped[Optional[int]] = mapped_column(INT)  # e.g. 2024 for 24/25

    # Relationships
    races: Mapped[list["Race"]] = relationship("Race", back_populates="meeting", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("date", "venue_code", name="uq_meeting_date_venue"),
        Index("idx_meeting_date", "date"),
    )

    def __repr__(self) -> str:
        return f"<Meeting(id={self.id}, date={self.date}, venue={self.venue_code})>"


class Race(Base):
    __tablename__ = "race"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("meeting.id", ondelete="CASCADE"), nullable=False)
    race_no: Mapped[int] = mapped_column(INT, nullable=False)
    race_code: Mapped[Optional[int]] = mapped_column(INT)  # Changed from VARCHAR(16)
    name_cn: Mapped[Optional[str]] = mapped_column(VARCHAR(128))
    class_text: Mapped[Optional[str]] = mapped_column(VARCHAR(32))
    distance_m: Mapped[Optional[int]] = mapped_column(INT)
    track_type: Mapped[Optional[str]] = mapped_column(VARCHAR(16))  # 草地/泥地
    track_course: Mapped[Optional[str]] = mapped_column(VARCHAR(8))  # A, A+3, C+3
    going: Mapped[Optional[str]] = mapped_column(VARCHAR(32))
    prize_total: Mapped[Optional[int]] = mapped_column(INT)
    final_time_str: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    localresults_url: Mapped[Optional[str]] = mapped_column(TEXT)
    sectional_url: Mapped[Optional[str]] = mapped_column(TEXT)

    # Relationships
    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="races")
    runners: Mapped[list["Runner"]] = relationship("Runner", back_populates="race", cascade="all, delete-orphan")
    horse_sectionals: Mapped[list["HorseSectional"]] = relationship("HorseSectional", back_populates="race", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("meeting_id", "race_no", name="uq_race_meeting_raceno"),
        Index("idx_race_meeting", "meeting_id"),
    )

    def __repr__(self) -> str:
        return f"<Race(id={self.id}, meeting_id={self.meeting_id}, race_no={self.race_no}, name={self.name_cn})>"


# ============================================================================
# 馬匹與 Profile（含歷史）(Horses and Profiles)
# ============================================================================

class Horse(Base):
    __tablename__ = "horse"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(VARCHAR(16), unique=True, nullable=False)
    name_cn: Mapped[Optional[str]] = mapped_column(VARCHAR(128))
    name_en: Mapped[Optional[str]] = mapped_column(VARCHAR(128))
    hkjc_horse_id: Mapped[Optional[str]] = mapped_column(VARCHAR(32), unique=True)
    profile_url: Mapped[Optional[str]] = mapped_column(TEXT)

    # Relationships
    profile: Mapped[Optional["HorseProfile"]] = relationship("HorseProfile", back_populates="horse", uselist=False, cascade="all, delete-orphan")
    profile_history: Mapped[list["HorseProfileHistory"]] = relationship("HorseProfileHistory", back_populates="horse", cascade="all, delete-orphan")
    runners: Mapped[list["Runner"]] = relationship("Runner", back_populates="horse", cascade="all, delete-orphan")
    sectionals: Mapped[list["HorseSectional"]] = relationship("HorseSectional", back_populates="horse", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_horse_code", "code"),
        Index("idx_horse_hkjc_id", "hkjc_horse_id"),
    )

    def __repr__(self) -> str:
        return f"<Horse(id={self.id}, code={self.code}, name={self.name_cn})>"


class HorseProfile(Base):
    __tablename__ = "horse_profile"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    horse_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("horse.id", ondelete="CASCADE"), unique=True, nullable=False)
    origin: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    age: Mapped[Optional[int]] = mapped_column(INT)
    colour: Mapped[Optional[str]] = mapped_column(VARCHAR(32))
    sex: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    import_type: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    season_prize_hkd: Mapped[Optional[int]] = mapped_column(INT)
    lifetime_prize_hkd: Mapped[Optional[int]] = mapped_column(INT)
    record_wins: Mapped[Optional[int]] = mapped_column(INT)
    record_seconds: Mapped[Optional[int]] = mapped_column(INT)
    record_thirds: Mapped[Optional[int]] = mapped_column(INT)
    record_starts: Mapped[Optional[int]] = mapped_column(INT)
    last10_starts: Mapped[Optional[int]] = mapped_column(INT)
    current_location: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    current_location_date: Mapped[Optional[date]] = mapped_column(DATE)
    import_date: Mapped[Optional[date]] = mapped_column(DATE)
    owner_name: Mapped[Optional[str]] = mapped_column(VARCHAR(128))
    current_rating: Mapped[Optional[int]] = mapped_column(INT)
    season_start_rating: Mapped[Optional[int]] = mapped_column(INT)
    sire_name: Mapped[Optional[str]] = mapped_column(VARCHAR(128))
    dam_name: Mapped[Optional[str]] = mapped_column(VARCHAR(128))
    dam_sire_name: Mapped[Optional[str]] = mapped_column(VARCHAR(128))

    # Relationships
    horse: Mapped["Horse"] = relationship("Horse", back_populates="profile")

    def __repr__(self) -> str:
        return f"<HorseProfile(horse_id={self.horse_id}, rating={self.current_rating})>"


class HorseProfileHistory(Base):
    __tablename__ = "horse_profile_history"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    horse_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("horse.id", ondelete="CASCADE"), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    origin: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    age: Mapped[Optional[int]] = mapped_column(INT)
    colour: Mapped[Optional[str]] = mapped_column(VARCHAR(32))
    sex: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    import_type: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    season_prize_hkd: Mapped[Optional[int]] = mapped_column(INT)
    lifetime_prize_hkd: Mapped[Optional[int]] = mapped_column(INT)
    record_wins: Mapped[Optional[int]] = mapped_column(INT)
    record_seconds: Mapped[Optional[int]] = mapped_column(INT)
    record_thirds: Mapped[Optional[int]] = mapped_column(INT)
    record_starts: Mapped[Optional[int]] = mapped_column(INT)
    last10_starts: Mapped[Optional[int]] = mapped_column(INT)
    current_location: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    current_location_date: Mapped[Optional[date]] = mapped_column(DATE)
    import_date: Mapped[Optional[date]] = mapped_column(DATE)
    owner_name: Mapped[Optional[str]] = mapped_column(VARCHAR(128))
    current_rating: Mapped[Optional[int]] = mapped_column(INT)
    season_start_rating: Mapped[Optional[int]] = mapped_column(INT)
    sire_name: Mapped[Optional[str]] = mapped_column(VARCHAR(128))
    dam_name: Mapped[Optional[str]] = mapped_column(VARCHAR(128))
    dam_sire_name: Mapped[Optional[str]] = mapped_column(VARCHAR(128))

    # Relationships
    horse: Mapped["Horse"] = relationship("Horse", back_populates="profile_history")

    __table_args__ = (
        UniqueConstraint("horse_id", "captured_at", name="uq_horse_profile_history_horse_captured"),
        Index("idx_horse_profile_history_horse_captured", "horse_id", "captured_at"),
    )

    def __repr__(self) -> str:
        return f"<HorseProfileHistory(horse_id={self.horse_id}, captured_at={self.captured_at})>"


# ============================================================================
# 騎師與練馬師 (Jockeys and Trainers)
# ============================================================================

class Jockey(Base):
    __tablename__ = "jockey"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(VARCHAR(16), unique=True, nullable=False)
    name_cn: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    name_en: Mapped[Optional[str]] = mapped_column(VARCHAR(64))

    # Relationships
    runners: Mapped[list["Runner"]] = relationship("Runner", back_populates="jockey")

    __table_args__ = (
        Index("idx_jockey_code", "code"),
    )

    def __repr__(self) -> str:
        return f"<Jockey(id={self.id}, code={self.code}, name={self.name_cn})>"


class Trainer(Base):
    __tablename__ = "trainer"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(VARCHAR(16), unique=True, nullable=False)
    name_cn: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    name_en: Mapped[Optional[str]] = mapped_column(VARCHAR(64))

    # Relationships
    runners: Mapped[list["Runner"]] = relationship("Runner", back_populates="trainer")

    __table_args__ = (
        Index("idx_trainer_code", "code"),
    )

    def __repr__(self) -> str:
        return f"<Trainer(id={self.id}, code={self.code}, name={self.name_cn})>"


# ============================================================================
# 每場每馬成績與分段 (Runner Performance and Sectionals)
# ============================================================================

class Runner(Base):
    __tablename__ = "runner"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    race_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("race.id", ondelete="CASCADE"), nullable=False)
    horse_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("horse.id", ondelete="CASCADE"), nullable=False)
    jockey_id: Mapped[Optional[int]] = mapped_column(BIGINT, ForeignKey("jockey.id", ondelete="SET NULL"))
    trainer_id: Mapped[Optional[int]] = mapped_column(BIGINT, ForeignKey("trainer.id", ondelete="SET NULL"))
    finish_position_raw: Mapped[Optional[str]] = mapped_column(VARCHAR(8))
    finish_position_num: Mapped[Optional[int]] = mapped_column(INT)
    horse_no: Mapped[Optional[int]] = mapped_column(INT)
    actual_weight: Mapped[Optional[int]] = mapped_column(INT)
    declared_weight: Mapped[Optional[int]] = mapped_column(INT)
    draw: Mapped[Optional[int]] = mapped_column(INT)
    margin_raw: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    running_pos_raw: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    finish_time_str: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    win_odds: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(8, 2))

    # Relationships
    race: Mapped["Race"] = relationship("Race", back_populates="runners")
    horse: Mapped["Horse"] = relationship("Horse", back_populates="runners")
    jockey: Mapped[Optional["Jockey"]] = relationship("Jockey", back_populates="runners")
    trainer: Mapped[Optional["Trainer"]] = relationship("Trainer", back_populates="runners")
    sectionals: Mapped[list["HorseSectional"]] = relationship("HorseSectional", back_populates="runner", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("race_id", "horse_id", name="uq_runner_race_horse"),
        Index("idx_runner_race", "race_id"),
        Index("idx_runner_horse", "horse_id"),
        Index("idx_runner_jockey", "jockey_id"),
        Index("idx_runner_trainer", "trainer_id"),
    )

    def __repr__(self) -> str:
        return f"<Runner(id={self.id}, race_id={self.race_id}, horse_id={self.horse_id}, position={self.finish_position_raw})>"


class HorseSectional(Base):
    __tablename__ = "horse_sectional"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    race_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("race.id", ondelete="CASCADE"), nullable=False)
    runner_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("runner.id", ondelete="CASCADE"), nullable=False)
    horse_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("horse.id", ondelete="CASCADE"), nullable=False)
    section_no: Mapped[int] = mapped_column(INT, nullable=False)
    position: Mapped[Optional[int]] = mapped_column(INT)
    margin_raw: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    time_main: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(6, 2))
    time_sub1: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(6, 2))
    time_sub2: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(6, 2))
    time_sub3: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(6, 2))
    finish_time_str: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    raw_cell: Mapped[Optional[str]] = mapped_column(VARCHAR(64))

    # Relationships
    race: Mapped["Race"] = relationship("Race", back_populates="horse_sectionals")
    runner: Mapped["Runner"] = relationship("Runner", back_populates="sectionals")
    horse: Mapped["Horse"] = relationship("Horse", back_populates="sectionals")

    __table_args__ = (
        UniqueConstraint("runner_id", "section_no", name="uq_horse_sectional_runner_section"),
        Index("idx_horse_sectional_race", "race_id"),
        Index("idx_horse_sectional_runner", "runner_id"),
        Index("idx_horse_sectional_horse", "horse_id"),
    )

    def __repr__(self) -> str:
        return f"<HorseSectional(id={self.id}, runner_id={self.runner_id}, section={self.section_no}, position={self.position})>"
