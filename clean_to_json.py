#!/usr/bin/env python3
"""
CONLAB / Visionary Hub – Klima-Datenpipeline
Bereinigt heterogene Klima-CSVs/Excel zu sauberem, D3-fertigem JSON (Long/Tidy-Format).
"""
import pandas as pd, numpy as np, json, os, re

SRC = "/mnt/user-data/uploads"
OUT = "/home/claude/work/data"
os.makedirs(OUT, exist_ok=True)
manifest = {}

def save(name, df, desc, narrative):
    # NaN -> None (gültiges JSON null), Records-Orientierung für d3.json()
    df = df.replace({np.nan: None})
    recs = df.to_dict(orient="records")
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(recs, f, ensure_ascii=False, indent=2)
    manifest[name] = {"rows": len(recs), "columns": list(df.columns),
                      "description": desc, "narrative": narrative}
    print(f"  ✓ {name:42s} {len(recs):>6} rows  cols={list(df.columns)}")

print("== VERGANGENHEIT: Temperatur & CO2 ==")

# 1) OWID Temperatur-Anomalie (bereits long) -----------------------------
df = pd.read_csv(f"{SRC}/temperature-anomaly.csv")
df = df.rename(columns={"Entity":"entity","Code":"code","Year":"year",
                        "Average":"anomaly_c","Lower bound":"lower_c","Upper bound":"upper_c"})
df["year"] = df["year"].astype(int)
save("temperature_anomaly.json", df,
     "Globale/hemisphärische Temperaturanomalie (°C) ggü. Referenzperiode, mit Unsicherheitsband",
     "past")

# 2) NASA GISTEMP (wide -> long; *** = fehlend) --------------------------
g = pd.read_csv(f"{SRC}/NASA_GISS_Surface_Temperature_Analysis__GISTEMP_v4_.csv",
                skiprows=1, na_values=["***","****"])
g["Year"] = g["Year"].astype(int)
months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
m = g.melt(id_vars=["Year"], value_vars=months, var_name="month", value_name="anomaly_c")
m["month_num"] = m["month"].map({mn:i+1 for i,mn in enumerate(months)})
m = m.dropna(subset=["anomaly_c"]).sort_values(["Year","month_num"])
m = m.rename(columns={"Year":"year"})[["year","month","month_num","anomaly_c"]]
save("gistemp_monthly.json", m,
     "NASA GISTEMP v4 monatliche globale Temperaturanomalie (°C, Basis 1951-1980)", "past")
ann = g[["Year","J-D"]].rename(columns={"Year":"year","J-D":"anomaly_c"}).dropna()
ann["year"] = ann["year"].astype(int)
save("gistemp_annual.json", ann, "NASA GISTEMP v4 Jahresmittel-Anomalie (°C)", "past")

# 3) NOAA Global Land+Ocean Departure (# = Kommentar) --------------------
n = pd.read_csv(f"{SRC}/NOAA_Global_Land_and_Ocean_Average_Temperature_Departure.csv", comment="#")
n.columns = ["year","departure_c"]
n["year"] = n["year"].astype(int)
save("noaa_global_departure.json", n,
     "NOAA globale Land+Ozean Temperaturabweichung (°C, Basis 1901-2000)", "past")

# 4) NOAA CO2 Mauna Loa – jährlich ---------------------------------------
c = pd.read_csv(f"{SRC}/NOAA_co2_annmean_mlo.csv", comment="#")
c = c.rename(columns={"mean":"co2_ppm","unc":"uncertainty_ppm"})
c["year"] = c["year"].astype(int)
save("co2_annual.json", c, "NOAA Mauna Loa atmosphärisches CO2 Jahresmittel (ppm)", "past")

# 5) NOAA CO2 Mauna Loa – monatlich --------------------------------------
cm = pd.read_csv(f"{SRC}/NOAA_co2_monthly.csv", comment="#")
cm = cm[["year","month","decimal date","average","deseasonalized"]].copy()
cm.columns = ["year","month","decimal_date","co2_ppm","co2_deseasonalized_ppm"]
cm = cm.replace(-9.99, np.nan)
cm["year"] = cm["year"].astype(int); cm["month"] = cm["month"].astype(int)
save("co2_monthly.json", cm, "NOAA Mauna Loa monatliches CO2 (ppm)", "past")

print("== GEGENWART: Emissionen & Extremwetter (geografisch) ==")

# 6) ClimateWatch THG-Emissionen (wide -> long) --------------------------
e = pd.read_csv(f"{SRC}/climatewatch_ghg-emissions.csv")
year_cols = [c for c in e.columns if str(c).isdigit()]
el = e.melt(id_vars=["iso","Country/Region","unit"], value_vars=year_cols,
            var_name="year", value_name="emissions")
el = el.rename(columns={"Country/Region":"country"})
el["year"] = el["year"].astype(int)
el["emissions"] = pd.to_numeric(el["emissions"], errors="coerce")
el = el.dropna(subset=["emissions"])
save("ghg_emissions.json", el,
     "ClimateWatch Treibhausgas-Emissionen pro Land/Jahr (MtCO2e). iso = ISO3 für Karten-Join", "present")

# 7) NOAA Katastrophenkosten je Bundesstaat (wide -> long) ---------------
sc = pd.read_csv(f"{SRC}/NOAA_state-cost-data.csv", skiprows=1)
scl = sc.melt(id_vars=["state"], var_name="disaster_type", value_name="cost_million_usd")
scl["cost_million_usd"] = pd.to_numeric(scl["cost_million_usd"], errors="coerce")
save("disaster_cost_by_state.json", scl,
     "NOAA Billion-Dollar-Katastrophen Kosten je US-Bundesstaat 1980-2024 (Mio. USD, inflationsbereinigt)", "present")

# 8) NOAA Katastrophenhäufigkeit je Jahr/Staat (wide -> long) ------------
sf = pd.read_csv(f"{SRC}/NOAA_state-freq-data.csv", skiprows=1)
sfl = sf.melt(id_vars=["year","state"], var_name="disaster_type", value_name="count")
sfl["year"] = sfl["year"].astype(int)
sfl["count"] = pd.to_numeric(sfl["count"], errors="coerce").fillna(0).astype(int)
sfl = sfl[sfl["count"] > 0]
save("disaster_freq_by_year.json", sfl,
     "NOAA Katastrophen-Häufigkeit je US-Bundesstaat/Jahr/Typ (nur >0)", "present")

# 9) Climate Impact Lab – County-Schäden nach Sektor ---------------------
cs = pd.read_csv(f"{SRC}/Climate_Impact_Lab_county_damages_by_sector.csv")
cs.columns = ["state","county","fips","population_2012","income_2012",
              "agriculture_pct","mortality_per_100k","energy_pct","labor_lowrisk_pct",
              "labor_highrisk_pct","coastal_log10_pct","property_crime_pct",
              "violent_crime_pct","total_damages_pct"]
cs["fips"] = cs["fips"].astype(str).str.zfill(5)  # FIPS als 5-stelliger String für Karten-Join
save("county_damages_by_sector.json", cs,
     "Climate Impact Lab US-County Schäden nach Sektor (~+3°C Szenario). fips = 5-stellig für Choropleth", "present")

# 10) Climate Impact Lab – County Gesamtschaden nach Wahrscheinlichkeit ---
cl = pd.read_csv(f"{SRC}/Climate_Impact_Lab_county_total_damages_by_likelihood.csv")
cl.columns = ["state","county","fips","population_2012","income_2012",
              "p5","p17","median","p83","p95"]
cl["fips"] = cl["fips"].astype(str).str.zfill(5)
save("county_total_damages.json", cl,
     "Climate Impact Lab County Gesamtschaden (% County-Einkommen) als Perzentil-Verteilung", "present")

# 11) Income-Decile-Verteilung (klein) -----------------------------------
dd = pd.read_csv(f"{SRC}/Climate_Impact_Lab_decile_total_damages_distribution.csv")
dd.columns = ["income_decile","p5","p17","median","p83","p95"]
save("decile_distribution.json", dd,
     "Schadensverteilung nach Einkommens-Dezil (% Einkommen)", "present")

print("== ZUKUNFT: Projektionen (SSP-Szenarien) ==")

# 12) Climate Impact Lab Excel – Temperatur-Projektionen (Multi-Header) ---
xl = pd.ExcelFile(f"{SRC}/ClimateImpactLab_GlobalData_20March2023.xlsx")
tas_sheets = [s for s in xl.sheet_names if s.startswith(("tas_","tasmin","tasmax"))]
periods = ["historical_1986_2005","next_decades_2020_2039","midcentury_2040_2059","endcentury_2080_2099"]
percentiles = [0.05, 0.5, 0.95]
proj_rows = []
for s in tas_sheets:
    mvar = re.match(r"(tas|tasmin_under32F|tasmax_over95F)_?(annual|JJA|DJF)?_?(ssp[\d\.-]+)", s)
    raw = pd.read_excel(xl, s, header=None, skiprows=3)
    # Spalten: 0=ISO, dann 4 Perioden × 3 Perzentile
    parts = s.split("_")
    scenario = parts[-1]
    season = "annual" if "annual" in s else ("summer" if "JJA" in s else ("winter" if "DJF" in s else "annual"))
    variable = "tasmin_under32F" if "tasmin" in s else ("tasmax_over95F" if "tasmax" in s else "mean_temp")
    for _, row in raw.iterrows():
        iso = row[0]
        if not isinstance(iso, str): continue
        ci = 1
        for per in periods:
            for pc in percentiles:
                val = row[ci]; ci += 1
                if pd.notna(val):
                    proj_rows.append({"iso": iso, "variable": variable, "season": season,
                                      "scenario": scenario, "period": per, "percentile": pc,
                                      "value": float(val)})
proj = pd.DataFrame(proj_rows)
save("projections_temperature.json", proj,
     "Climate Impact Lab Temperatur-Projektionen je Land/Szenario/Periode/Perzentil (Vergangenheit→Jahrhundertende)", "future")

# Manifest schreiben
with open(f"{OUT}/manifest.json","w",encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print(f"\n  ✓ manifest.json ({len(manifest)} Datensätze)")
