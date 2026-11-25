"""Scan folder, load channel + MMP CSVs, join, validate. No Streamlit imports (testable alone)."""
import io
import re
from pathlib import Path

import pandas as pd

import config

FNAME = re.compile(r"^(\d{4}-\d{2}-\d{2})_(channel|appsflyer)\.csv$")
NUM_COLS = ["impressions", "cost",
            "clicks_ch", "signups_ch", "purchases_ch", "revenue_ch",
            "clicks_mmp", "signups_mmp", "purchases_mmp", "revenue_mmp"]


class Src:
    """One CSV: a file on disk, or uploaded bytes held only in memory."""

    def __init__(self, name: str, path: Path = None, data: bytes = None, mtime: int = 0):
        self.name, self.path, self.data, self.mtime = name, path, data, mtime

    def read(self) -> pd.DataFrame:
        for enc in ("utf-8-sig", "cp949"):
            try:
                return pd.read_csv(self.path if self.path else io.BytesIO(self.data), encoding=enc)
            except UnicodeDecodeError:
                continue
        raise ValueError(f"cannot decode {self.name}")


def scan(data_dir: Path) -> dict:
    """{'channel': {date_str: Src}, 'appsflyer': {...}} for files named YYYY-MM-DD_<kind>.csv."""
    out = {"channel": {}, "appsflyer": {}}
    for p in Path(data_dir).glob("*.csv"):
        m = FNAME.match(p.name)
        if m:
            out[m.group(2)][m.group(1)] = Src(p.name, path=p, mtime=p.stat().st_mtime_ns)
    return out


def scan_uploads(uploads) -> tuple:
    """uploads: iterable of (name, bytes). Later uploads win on same name. Returns (files, ignored_names)."""
    out, ignored = {"channel": {}, "appsflyer": {}}, []
    for i, (name, data) in enumerate(uploads):
        m = FNAME.match(name)
        if m:
            out[m.group(2)][m.group(1)] = Src(name, data=data, mtime=i)
        else:
            ignored.append(name)
    return out, ignored


def files_signature(data_dir: Path) -> tuple:
    """Changes whenever a matching file is added, removed or modified -> use as cache key."""
    files = scan(data_dir)
    return tuple(sorted((k, d, p.mtime, p.path.stat().st_size)
                        for k, v in files.items() for d, p in v.items()))


def _load_kind(files: dict, colmap: dict, issues: list) -> pd.DataFrame:
    frames = []
    for d, p in sorted(files.items()):
        try:
            df = p.read()
        except Exception as e:  # noqa: BLE001 - surface any read problem as an issue
            issues.append(("error", "read_failed", f"{p.name}: {e}"))
            continue
        missing = [c for c in colmap if c not in df.columns]
        if missing:
            issues.append(("error", "missing_columns", f"{p.name}: {missing}"))
            continue
        df = df[list(colmap)].rename(columns=colmap)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        bad = (df["date"].dt.strftime("%Y-%m-%d") != d).sum()
        if bad:
            issues.append(("warn", "date_mismatch", f"{p.name}: 파일명 날짜와 다른 '일' 값 {bad}행"))
        df["_mtime"] = p.mtime
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=list(colmap.values()))


def _dedupe(df: pd.DataFrame, label: str, issues: list) -> pd.DataFrame:
    if df.empty:
        return df
    dup = df.duplicated(config.KEYS, keep=False)
    if dup.any():
        issues.append(("warn", "duplicate_keys", f"{label}: 같은 키 {int(dup.sum())}행 중복 → 최신 파일 값 사용"))
    return (df.sort_values("_mtime").drop_duplicates(config.KEYS, keep="last")
              .drop(columns="_mtime"))


def load_all(data_dir=config.DATA_DIR, uploads=None):
    """Returns (joined_df, issues_df). joined_df.match in {both, channel_only, mmp_only}.
    uploads: optional list of (filename, bytes); when given, data_dir is not read."""
    issues: list = []
    if uploads is not None:
        files, ignored = scan_uploads(uploads)
        for n in ignored:
            issues.append(("warn", "ignored_file", f"{n}: 파일명이 YYYY-MM-DD_channel.csv / _appsflyer.csv 규칙이 아니라 무시됨"))
    else:
        files = scan(data_dir)

    for d in sorted(set(files["channel"]) ^ set(files["appsflyer"])):
        have = "channel" if d in files["channel"] else "appsflyer"
        miss = "appsflyer" if have == "channel" else "channel"
        issues.append(("warn", "missing_pair", f"{d}: {have}만 있고 {miss} 파일 없음"))

    ch = _dedupe(_load_kind(files["channel"], config.CHANNEL_COLS, issues), "channel", issues)
    mmp = _load_kind(files["appsflyer"], config.MMP_COLS, issues)
    if not mmp.empty:
        mapped = mmp["media_source"].map(config.MEDIA_SOURCE_MAP)
        unmapped = sorted(mmp.loc[mapped.isna(), "media_source"].unique())
        if unmapped:
            issues.append(("warn", "unmapped_media_source",
                           f"config.MEDIA_SOURCE_MAP에 없는 미디어소스: {unmapped}"))
        mmp["channel"] = mapped.fillna(mmp["media_source"])
        mmp = mmp.drop(columns="media_source")
    mmp = _dedupe(mmp, "appsflyer", issues)

    if ch.empty and mmp.empty:
        return pd.DataFrame(columns=config.KEYS + NUM_COLS + ["match"]), _issues_df(issues)

    df = ch.merge(mmp, on=config.KEYS, how="outer", indicator=True)
    df["match"] = df["_merge"].map({"both": "both", "left_only": "channel_only",
                                    "right_only": "mmp_only"}).astype(str)
    df = df.drop(columns="_merge")
    for c in NUM_COLS:
        df[c] = pd.to_numeric(df.get(c), errors="coerce").fillna(0)
    for c in ("channel_type", "objective"):
        df[c] = df[c].fillna("-") if c in df else "-"

    bad = df[df["match"] != "both"]
    for d, g in bad.groupby(bad["date"].dt.strftime("%Y-%m-%d")):
        n_ch, n_mmp = (g["match"] == "channel_only").sum(), (g["match"] == "mmp_only").sum()
        issues.append(("warn", "unmatched_rows", f"{d}: 매체에만 {n_ch}행, MMP에만 {n_mmp}행"))
    return df.sort_values(config.KEYS).reset_index(drop=True), _issues_df(issues)


def _issues_df(issues: list) -> pd.DataFrame:
    return pd.DataFrame(issues, columns=["level", "type", "detail"])


if __name__ == "__main__":
    pd.set_option("display.width", 200, "display.max_columns", 30, "display.max_colwidth", 120)
    d, i = load_all()
    print("rows:", len(d), "| dates:", d["date"].nunique() if len(d) else 0)
    print(d["match"].value_counts().to_dict() if len(d) else {})
    print(d[NUM_COLS].sum().astype("int64").to_string() if len(d) else "")
    print("issues:", "none" if i.empty else "\n" + i.to_string())
