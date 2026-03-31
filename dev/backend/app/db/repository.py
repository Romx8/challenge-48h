from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time, timezone

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.core.settings import Settings


class Repository:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.settings.database_url, row_factory=dict_row)

    def init_schema(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS air_readings (
            id BIGSERIAL PRIMARY KEY,
            station_code TEXT NOT NULL,
            city TEXT NOT NULL,
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL,
            observed_at TIMESTAMPTZ NOT NULL,
            index_value DOUBLE PRECISION NOT NULL,
            pollution_score DOUBLE PRECISION,
            meteo_modifier DOUBLE PRECISION,
            risk_level TEXT NOT NULL,
            pollutants JSONB NOT NULL,
            meteo JSONB NOT NULL,
            matched_meteo_station TEXT,
            station_distance_km DOUBLE PRECISION,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_air_readings_station_time UNIQUE (station_code, observed_at)
        );

        CREATE INDEX IF NOT EXISTS idx_air_readings_observed_at ON air_readings (observed_at DESC);
        CREATE INDEX IF NOT EXISTS idx_air_readings_index_value ON air_readings (index_value);
        CREATE INDEX IF NOT EXISTS idx_air_readings_geo ON air_readings (latitude, longitude);
        CREATE INDEX IF NOT EXISTS idx_air_readings_city ON air_readings (city);

        CREATE TABLE IF NOT EXISTS air_data_coverage (
            day_date DATE PRIMARY KEY,
            status TEXT NOT NULL,
            row_count INTEGER NOT NULL DEFAULT 0,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_air_data_coverage_status CHECK (status IN ('has_data', 'no_data'))
        );

        INSERT INTO air_data_coverage (day_date, status, row_count, fetched_at, updated_at)
        SELECT
            (observed_at AT TIME ZONE 'UTC')::date AS day_date,
            'has_data' AS status,
            COUNT(*)::INT AS row_count,
            NOW(),
            NOW()
        FROM air_readings
        GROUP BY 1
        ON CONFLICT (day_date)
        DO UPDATE SET
            status = 'has_data',
            row_count = GREATEST(air_data_coverage.row_count, EXCLUDED.row_count),
            updated_at = NOW();
        """
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(ddl)
            conn.commit()

    def upsert_readings(self, records: Iterable[dict]) -> int:
        rows = [self._to_row(record) for record in records]
        if not rows:
            return 0

        statement = """
        INSERT INTO air_readings (
            station_code,
            city,
            latitude,
            longitude,
            observed_at,
            index_value,
            pollution_score,
            meteo_modifier,
            risk_level,
            pollutants,
            meteo,
            matched_meteo_station,
            station_distance_km
        ) VALUES (
            %(station_code)s,
            %(city)s,
            %(latitude)s,
            %(longitude)s,
            %(observed_at)s,
            %(index_value)s,
            %(pollution_score)s,
            %(meteo_modifier)s,
            %(risk_level)s,
            %(pollutants)s,
            %(meteo)s,
            %(matched_meteo_station)s,
            %(station_distance_km)s
        )
        ON CONFLICT (station_code, observed_at)
        DO UPDATE SET
            city = EXCLUDED.city,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            index_value = EXCLUDED.index_value,
            pollution_score = EXCLUDED.pollution_score,
            meteo_modifier = EXCLUDED.meteo_modifier,
            risk_level = EXCLUDED.risk_level,
            pollutants = EXCLUDED.pollutants,
            meteo = EXCLUDED.meteo,
            matched_meteo_station = EXCLUDED.matched_meteo_station,
            station_distance_km = EXCLUDED.station_distance_km,
            updated_at = NOW();
        """
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.executemany(statement, rows)
            conn.commit()
        self.mark_coverage_from_records(rows)
        return len(rows)

    def get_uncovered_dates(self, start_date: date, end_date: date) -> list[date]:
        if start_date > end_date:
            return []

        statement = """
        SELECT day_ref::date AS day_date
        FROM generate_series(%(start_date)s::date, %(end_date)s::date, interval '1 day') AS day_ref
        LEFT JOIN air_data_coverage coverage
          ON coverage.day_date = day_ref::date
        WHERE coverage.day_date IS NULL
        ORDER BY day_ref
        """
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(statement, params)
                rows = cursor.fetchall()
        return [row["day_date"] for row in rows]

    def mark_coverage_for_dates(self, days: Iterable[date], counts_by_day: dict[date, int] | None = None) -> None:
        unique_days = sorted(set(days))
        if not unique_days:
            return

        counts = counts_by_day or {}
        rows = []
        for day_value in unique_days:
            day_count = max(0, int(counts.get(day_value, 0)))
            rows.append(
                {
                    "day_date": day_value,
                    "status": "has_data" if day_count > 0 else "no_data",
                    "row_count": day_count,
                }
            )

        statement = """
        INSERT INTO air_data_coverage (day_date, status, row_count, fetched_at, updated_at)
        VALUES (%(day_date)s, %(status)s, %(row_count)s, NOW(), NOW())
        ON CONFLICT (day_date)
        DO UPDATE SET
            status = CASE
                WHEN EXCLUDED.row_count > 0 OR air_data_coverage.row_count > 0 THEN 'has_data'
                ELSE 'no_data'
            END,
            row_count = GREATEST(air_data_coverage.row_count, EXCLUDED.row_count),
            fetched_at = NOW(),
            updated_at = NOW()
        """
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.executemany(statement, rows)
            conn.commit()

    def mark_coverage_from_records(self, records: Iterable[dict]) -> None:
        counts_by_day: dict[date, int] = {}
        for record in records:
            observed = record.get("observed_at")
            if observed is None:
                continue
            observed_day = _to_utc_date(observed)
            counts_by_day[observed_day] = counts_by_day.get(observed_day, 0) + 1

        if counts_by_day:
            self.mark_coverage_for_dates(counts_by_day.keys(), counts_by_day)

    def fetch_readings(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
        min_lat: float | None,
        max_lat: float | None,
        min_lng: float | None,
        max_lng: float | None,
        min_index: float | None,
        max_index: float | None,
        aggregate_by: str,
        limit: int,
    ) -> tuple[int, list[dict]]:
        where_clause, params = self._where_clause(
            start_date=start_date,
            end_date=end_date,
            min_lat=min_lat,
            max_lat=max_lat,
            min_lng=min_lng,
            max_lng=max_lng,
            min_index=min_index,
            max_index=max_index,
            limit=limit,
        )

        if aggregate_by == "city":
            return self._fetch_city_aggregate(where_clause, params)
        return self._fetch_raw(where_clause, params)

    def _fetch_raw(self, where_clause: str, params: dict) -> tuple[int, list[dict]]:
        count_query = f"SELECT COUNT(*) AS total FROM air_readings WHERE {where_clause}"
        data_query = f"""
            SELECT
                station_code AS "stationCode",
                city,
                latitude,
                longitude,
                ROUND(index_value::numeric, 2) AS aqi,
                observed_at AS "measuredAt",
                risk_level AS "riskLevel",
                NULL::INT AS "sampleSize"
            FROM air_readings
            WHERE {where_clause}
            ORDER BY observed_at DESC
            LIMIT %(limit)s
        """

        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(count_query, params)
                total = int(cursor.fetchone()["total"])
                cursor.execute(data_query, params)
                rows = cursor.fetchall()
        return total, rows

    def _fetch_city_aggregate(self, where_clause: str, params: dict) -> tuple[int, list[dict]]:
        count_query = f"""
            SELECT COUNT(*) AS total
            FROM (
                SELECT city
                FROM air_readings
                WHERE {where_clause}
                GROUP BY city
            ) grouped
        """
        data_query = f"""
            SELECT
                NULL::TEXT AS "stationCode",
                city,
                ROUND(AVG(latitude)::numeric, 6) AS latitude,
                ROUND(AVG(longitude)::numeric, 6) AS longitude,
                ROUND(AVG(index_value)::numeric, 2) AS aqi,
                MAX(observed_at) AS "measuredAt",
                NULL::TEXT AS "riskLevel",
                COUNT(*)::INT AS "sampleSize"
            FROM air_readings
            WHERE {where_clause}
            GROUP BY city
            ORDER BY "measuredAt" DESC
            LIMIT %(limit)s
        """

        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(count_query, params)
                total = int(cursor.fetchone()["total"])
                cursor.execute(data_query, params)
                rows = cursor.fetchall()
        return total, rows

    @staticmethod
    def _to_row(record: dict) -> dict:
        city = record.get("matched_meteo_station") or record.get("station_code")

        return {
            "station_code": str(record["station_code"]),
            "city": str(city),
            "latitude": float(record["latitude"]),
            "longitude": float(record["longitude"]),
            "observed_at": record["observed_at"],
            "index_value": float(record["index"]),
            "pollution_score": _nullable_float(record.get("pollution_score")),
            "meteo_modifier": _nullable_float(record.get("meteo_modifier")),
            "risk_level": str(record["risk_level"]),
            "pollutants": Jsonb(record.get("pollutants") or {}),
            "meteo": Jsonb(record.get("meteo") or {}),
            "matched_meteo_station": record.get("matched_meteo_station"),
            "station_distance_km": _nullable_float(record.get("station_distance_km")),
        }

    @staticmethod
    def _where_clause(
        *,
        start_date: date | None,
        end_date: date | None,
        min_lat: float | None,
        max_lat: float | None,
        min_lng: float | None,
        max_lng: float | None,
        min_index: float | None,
        max_index: float | None,
        limit: int,
    ) -> tuple[str, dict]:
        conditions: list[str] = ["TRUE"]
        params: dict[str, object] = {"limit": max(1, min(limit, 2000))}

        if start_date:
            params["start_ts"] = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
            conditions.append("observed_at >= %(start_ts)s")
        if end_date:
            params["end_ts"] = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
            conditions.append("observed_at <= %(end_ts)s")

        if min_lat is not None:
            params["min_lat"] = min_lat
            conditions.append("latitude >= %(min_lat)s")
        if max_lat is not None:
            params["max_lat"] = max_lat
            conditions.append("latitude <= %(max_lat)s")
        if min_lng is not None:
            params["min_lng"] = min_lng
            conditions.append("longitude >= %(min_lng)s")
        if max_lng is not None:
            params["max_lng"] = max_lng
            conditions.append("longitude <= %(max_lng)s")

        if min_index is not None:
            params["min_index"] = min_index
            conditions.append("index_value >= %(min_index)s")
        if max_index is not None:
            params["max_index"] = max_index
            conditions.append("index_value <= %(max_index)s")

        return " AND ".join(conditions), params


def _nullable_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _to_utc_date(value: object) -> date:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).date()
        return value.astimezone(timezone.utc).date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            else:
                parsed = parsed.astimezone(timezone.utc)
            return parsed.date()
        except ValueError:
            return date.fromisoformat(text)
    raise ValueError(f"Type de date non supporté: {type(value)!r}")
