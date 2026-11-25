"""KPI and gap calculations. Gap = MMP / channel - 1, in percent."""
import numpy as np
import pandas as pd

SUM_COLS = ["impressions", "cost",
            "clicks_ch", "signups_ch", "purchases_ch", "revenue_ch",
            "clicks_mmp", "signups_mmp", "purchases_mmp", "revenue_mmp"]
GAP_METRICS = ["clicks", "signups", "purchases", "revenue"]


def safe_div(a, b):
    a = pd.Series(a, dtype="float64") if not isinstance(a, pd.Series) else a.astype("float64")
    b = pd.Series(b, dtype="float64") if not isinstance(b, pd.Series) else b.astype("float64")
    return a / b.where(b != 0)


def add_derived(g: pd.DataFrame) -> pd.DataFrame:
    for s in ("ch", "mmp"):
        g[f"ctr_{s}"] = safe_div(g[f"clicks_{s}"], g["impressions"]) * 100
        g[f"cpc_{s}"] = safe_div(g["cost"], g[f"clicks_{s}"])
        g[f"cpa_signup_{s}"] = safe_div(g["cost"], g[f"signups_{s}"])
        g[f"cpa_purchase_{s}"] = safe_div(g["cost"], g[f"purchases_{s}"])
        g[f"roas_{s}"] = safe_div(g[f"revenue_{s}"], g["cost"]) * 100
    for m in GAP_METRICS:
        g[f"gap_{m}"] = (safe_div(g[f"{m}_mmp"], g[f"{m}_ch"]) - 1) * 100
    return g


def aggregate(df: pd.DataFrame, by=None) -> pd.DataFrame:
    """Sum base metrics (optionally grouped) and add derived KPIs + gaps."""
    if by:
        g = df.groupby(by, dropna=False)[SUM_COLS].sum().reset_index()
    else:
        g = df[SUM_COLS].sum().to_frame().T
    return add_derived(g)


def col(metric: str, src: str) -> str:
    """Column name for a metric under a source ('ch' or 'mmp'). cost/impressions are channel-only."""
    return metric if metric in ("cost", "impressions") else f"{metric}_{src}"


def pct(x) -> str:
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:+.1f}%"
