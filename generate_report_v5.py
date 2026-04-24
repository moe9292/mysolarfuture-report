#!/usr/bin/env python3
"""
mySolarFuture – Solar-Empfehlungsbericht v5
Product catalog with auto-selection, roof/balcony split.
DC-coupled BKW physics, 800W inverter bottleneck, smart meter.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

# ─── CI ──────────────────────────────────────────────────────────────
C_PRIMARY = HexColor("#26455f")
C_ACCENT = HexColor("#6ce1b7")
C_ACCENT_DARK = HexColor("#4dc49a")
C_BLUE = HexColor("#3B82F6")
C_DARK = HexColor("#111827")
C_GRAY = HexColor("#6B7280")
C_LIGHT = HexColor("#F3F4F6")
C_WHITE = HexColor("#FFFFFF")
C_RED = HexColor("#EF4444")
C_BG_LIGHT = HexColor("#EFF8F4")
C_BG_ACCENT = HexColor("#F0FDF8")
W, H = A4

# ─── PRODUCT CATALOG ─────────────────────────────────────────────────

CATALOG_DACH = [
    {"id": "smart",  "label": "Solar Smart",  "modules": 4, "battery": 1.92, "cost": 3499, "fit": 0.0},
    {"id": "smart+", "label": "Solar Smart+", "modules": 4, "battery": 3.84, "cost": 4099, "fit": 0.0},
    {"id": "pro",    "label": "Solar Pro",    "modules": 6, "battery": 2.70, "cost": 5899, "fit": 0.0778},
    {"id": "max",    "label": "Solar Max",    "modules": 8, "battery": 2.70, "cost": 6899, "fit": 0.0778},
    {"id": "max+",   "label": "Solar Max+",   "modules": 8, "battery": 5.40, "cost": 7699, "fit": 0.0778},
]

CATALOG_BALKON = [
    {"id": "balkon",  "label": "Solar Balkon",  "modules": 2, "battery": 0.0,  "cost": 1899, "fit": 0.0},
    {"id": "balkon+", "label": "Solar Balkon+", "modules": 2, "battery": 1.92, "cost": 2899, "fit": 0.0},
]

# Selection: pick 3 from CATALOG_DACH based on consumption
# Always include at least one of Smart/Smart+
def select_packages(annual_consumption, max_modules=None):
    # Filter by max_modules if set
    available = CATALOG_DACH
    if max_modules:
        available = [p for p in available if p["modules"] <= max_modules]
        ids = [p["id"] for p in available]
        return ids[:3]  # return up to 3

    if annual_consumption <= 2000:
        return ["smart", "smart+", "pro"]
    elif annual_consumption <= 3000:
        return ["smart+", "pro", "max"]
    else:
        return ["smart+", "max", "max+"]

BIFACIAL = {"Schraegdach": 1.03, "Flachdach": 1.08, "Balkon": 1.07}

# ─── SOLAR DATA ──────────────────────────────────────────────────────
MONTHLY_DAILY_KWH_PER_KWP = [0.7, 1.2, 2.4, 3.6, 4.3, 4.6, 4.4, 4.0, 2.95, 1.7, 0.8, 0.5]
SOLAR_SHAPE = [
    0, 0, 0, 0, 0, 0.02, 0.05, 0.08, 0.10, 0.12, 0.13, 0.13,
    0.12, 0.11, 0.09, 0.06, 0.04, 0.02, 0.01, 0, 0, 0, 0, 0
]
LOAD_SHAPE = [
    0.022, 0.018, 0.016, 0.015, 0.015, 0.018, 0.035, 0.052, 0.050, 0.048, 0.050, 0.052,
    0.058, 0.052, 0.048, 0.045, 0.048, 0.055, 0.065, 0.062, 0.058, 0.050, 0.042, 0.030
]
MONTHLY_LOAD_FACTOR = [1.15, 1.10, 1.02, 0.95, 0.88, 0.82, 0.80, 0.82, 0.90, 1.00, 1.10, 1.18]
DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
MONTH_NAMES = ["Jan", "Feb", "M\xe4r", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


# ─── SIMULATION ──────────────────────────────────────────────────────

def simulate(module_count, module_wp, battery_kwh, max_inverter_w,
             annual_consumption, electricity_price, feed_in_tariff,
             system_cost, bifacial_gain=1.0,
             degradation_rate=0.004, price_increase_rate=0.025):

    total_kwp = (module_count * module_wp) / 1000
    system_eff = 0.965      # 1% cable + 2.5% soiling
    inverter_eff = 0.96
    charge_eff = 0.96       # Zendure GaN DC-coupled
    discharge_eff = 0.96
    min_soc = battery_kwh * 0.05 if battery_kwh > 0 else 0
    max_inv_ac = max_inverter_w / 1000

    solar_shape_sum = sum(SOLAR_SHAPE)
    norm_solar = [s / solar_shape_sum for s in SOLAR_SHAPE]
    load_shape_sum = sum(LOAD_SHAPE)
    load_factor_weighted = sum(d * f for d, f in zip(DAYS_IN_MONTH, MONTHLY_LOAD_FACTOR))

    CLEAR_FRAC = 0.40
    CLEAR_MULT = 1.45
    CLOUDY_MULT = 0.70

    # Stundenbasierte Peak-Korrektur: Anteil des Eigenverbrauchs, der in der Realität
    # durch kurzfristige Lastspitzen (>800W) aus dem Netz bezogen wird.
    # Nur in Stunden mit typischen Großverbrauchern (Kochen, Wasserkocher, Fön).
    PEAK_CORR = [
    #   0     1     2     3     4     5     6     7     8     9    10    11
        0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.05, 0.08, 0.00, 0.00, 0.00, 0.05,
    #  12    13    14    15    16    17    18    19    20    21    22    23
        0.12, 0.05, 0.00, 0.00, 0.00, 0.08, 0.12, 0.08, 0.04, 0.00, 0.00, 0.00,
    ]

    soc = battery_kwh * 0.15 if battery_kwh > 0 else 0
    T = {k: 0.0 for k in ['gen_dc','self_ac','feed_ac','grid_ac','curt_dc','batt_in_dc','batt_out_dc']}
    monthly = []

    for m in range(12):
        days = DAYS_IN_MONTH[m]
        avg_daily_dc = MONTHLY_DAILY_KWH_PER_KWP[m] * total_kwp * system_eff * bifacial_gain
        daily_load_ac = (annual_consumption / load_factor_weighted) * MONTHLY_LOAD_FACTOR[m]
        M = {k: 0.0 for k in T}
        clear_days = round(days * CLEAR_FRAC)
        cloudy_days = days - clear_days

        for n_days, mult in [(clear_days, CLEAR_MULT), (cloudy_days, CLOUDY_MULT)]:
            daily_dc = avg_daily_dc * mult
            for _ in range(n_days):
                for h in range(24):
                    pv_dc = daily_dc * norm_solar[h]
                    load_ac = daily_load_ac * (LOAD_SHAPE[h] / load_shape_sum)
                    T['gen_dc'] += pv_dc; M['gen_dc'] += pv_dc
                    prev_self = T['self_ac']

                    if battery_kwh > 0:
                        space = max(0, (battery_kwh - soc) / charge_eff)
                        charge = min(pv_dc, space)
                        soc += charge * charge_eff
                        pv_excess = pv_dc - charge
                        T['batt_in_dc'] += charge; M['batt_in_dc'] += charge

                        if pv_excess > 0.001:
                            inv_dc_cap = max_inv_ac / inverter_eff
                            inv_dc_in = min(pv_excess, inv_dc_cap)
                            inv_ac_out = inv_dc_in * inverter_eff
                            curtailed = pv_excess - inv_dc_in
                            to_house = min(inv_ac_out, load_ac)
                            to_grid = inv_ac_out - to_house
                            remaining = load_ac - to_house
                            headroom = max_inv_ac - inv_ac_out
                            if remaining > 0.001 and headroom > 0.001:
                                ba = max(0, soc - min_soc)
                                bd = min(remaining/(discharge_eff*inverter_eff), ba, headroom/inverter_eff)
                                bac = bd * discharge_eff * inverter_eff
                                soc -= bd; to_house += bac; remaining -= bac
                                T['batt_out_dc'] += bd; M['batt_out_dc'] += bd
                            T['self_ac'] += to_house; M['self_ac'] += to_house
                            T['feed_ac'] += to_grid; M['feed_ac'] += to_grid
                            T['curt_dc'] += curtailed; M['curt_dc'] += curtailed
                            T['grid_ac'] += max(0, remaining); M['grid_ac'] += max(0, remaining)
                        else:
                            ba = max(0, soc - min_soc)
                            bd = min(load_ac/(discharge_eff*inverter_eff), ba, max_inv_ac/inverter_eff)
                            bac = bd * discharge_eff * inverter_eff
                            soc -= bd
                            T['self_ac'] += bac; M['self_ac'] += bac
                            T['batt_out_dc'] += bd; M['batt_out_dc'] += bd
                            T['grid_ac'] += max(0, load_ac - bac); M['grid_ac'] += max(0, load_ac - bac)
                    else:
                        # No battery: PV → inverter → house/grid
                        inv_dc_cap = max_inv_ac / inverter_eff
                        inv_dc_in = min(pv_dc, inv_dc_cap)
                        inv_ac_out = inv_dc_in * inverter_eff
                        curtailed = pv_dc - inv_dc_in
                        to_house = min(inv_ac_out, load_ac)
                        to_grid = inv_ac_out - to_house
                        remaining = load_ac - to_house
                        T['self_ac'] += to_house; M['self_ac'] += to_house
                        T['feed_ac'] += to_grid; M['feed_ac'] += to_grid
                        T['curt_dc'] += curtailed; M['curt_dc'] += curtailed
                        T['grid_ac'] += remaining; M['grid_ac'] += remaining

                    # Stündliche Peak-Korrektur anwenden
                    pc = PEAK_CORR[h]
                    if pc > 0:
                        hour_self = T['self_ac'] - prev_self
                        shift = hour_self * pc
                        if shift > 0:
                            T['self_ac'] -= shift; M['self_ac'] -= shift
                            T['grid_ac'] += shift; M['grid_ac'] += shift

        monthly.append(M)

    gen_ac = T['gen_dc'] * inverter_eff
    self_rate = (T['self_ac'] / gen_ac * 100) if gen_ac > 0 else 0
    autarky = (T['self_ac'] / annual_consumption * 100) if annual_consumption > 0 else 0
    annual_savings = T['self_ac'] * electricity_price + T['feed_ac'] * feed_in_tariff

    cum = 0.0; amort = None; yearly = []
    for y in range(1, 26):
        deg = (1 - degradation_rate) ** (y - 1)
        pf = (1 + price_increase_rate) ** (y - 1)
        ys = T['self_ac'] * deg * electricity_price * pf + T['feed_ac'] * deg * feed_in_tariff
        cum += ys
        yearly.append({"year": y, "cum": cum, "annual": ys})
        if amort is None and cum >= system_cost:
            amort = y

    return {
        "gen_dc": round(T['gen_dc']), "self_ac": round(T['self_ac']),
        "feed_ac": round(T['feed_ac']), "grid_ac": round(T['grid_ac']),
        "curt_dc": round(T['curt_dc']),
        "autarky": round(autarky, 1), "self_rate": round(self_rate, 1),
        "savings": round(annual_savings), "avg_savings_25": round(cum / 25),
        "amort": amort, "cost": system_cost,
        "yearly": yearly, "monthly": monthly,
        "kwp": total_kwp, "modules": module_count, "battery": battery_kwh,
        "profit_25": round(cum - system_cost), "cum_25": round(cum),
        "feed_in_tariff": feed_in_tariff,
        "bifacial_gain": bifacial_gain, "system_eff": system_eff,
    }


# ─── PDF HELPERS ─────────────────────────────────────────────────────

def fmt(n): return f"{n:,.0f}".replace(",", ".")

def draw_header(c, pn, tp):
    c.setFillColor(C_PRIMARY); c.rect(0, H-28*mm, W, 28*mm, fill=1, stroke=0)
    c.setFillColor(C_ACCENT); c.rect(0, H-29*mm, W, 1*mm, fill=1, stroke=0)
    c.setFillColor(C_WHITE); c.setFont("Helvetica-Bold", 16)
    c.drawString(20*mm, H-14*mm, "mySolarFuture")
    c.setFont("Helvetica", 8)
    c.drawString(20*mm, H-20*mm, "Green Circuits GmbH  \xb7  Feldhusstr. 1, 27755 Delmenhorst")
    c.drawRightString(W-20*mm, H-20*mm, f"Seite {pn}/{tp}")

def draw_footer(c):
    c.setFillColor(C_LIGHT); c.rect(0, 0, W, 12*mm, fill=1, stroke=0)
    c.setFillColor(C_GRAY); c.setFont("Helvetica", 6.5)
    c.drawString(20*mm, 5*mm, "Green Circuits GmbH  \xb7  kontakt@mysolarfuture.de  \xb7  www.mysolarfuture.de")
    c.drawRightString(W-20*mm, 5*mm, "950 kWh/kWp (VZ Bremen)  \xb7  Lastprofil H0  \xb7  Angaben ohne Gew\xe4hr")

def rrect(c, x, y, w, h, r, fill, stroke=None):
    c.saveState(); c.setFillColor(fill)
    if stroke: c.setStrokeColor(stroke); c.setLineWidth(0.5); c.roundRect(x,y,w,h,r,fill=1,stroke=1)
    else: c.roundRect(x,y,w,h,r,fill=1,stroke=0)
    c.restoreState()

def draw_badge(c, x, y, label, modules, battery, cost, color, badge_text=None):
    bw, bh = 52*mm, 33*mm if badge_text else 30*mm
    rrect(c, x, y, bw, bh, 3*mm, C_WHITE, color if badge_text else HexColor("#D1D5DB"))
    if badge_text:
        c.setFillColor(color)
        tw = c.stringWidth(badge_text, "Helvetica-Bold", 5.5) + 6*mm
        c.roundRect(x+26*mm-tw/2, y+bh-2*mm, tw, 5*mm, 2*mm, fill=1, stroke=0)
        c.setFillColor(C_WHITE if color == C_PRIMARY else C_DARK)
        c.setFont("Helvetica-Bold", 5.5)
        c.drawCentredString(x+26*mm, y+bh-0.5*mm, badge_text)
    c.setFillColor(color); c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(x+26*mm, y+bh-9*mm, label)
    c.setFillColor(C_DARK); c.setFont("Helvetica", 7)
    c.drawCentredString(x+26*mm, y+bh-15*mm, f"{modules}\xd7 445 Wp")
    if battery > 0:
        c.drawCentredString(x+26*mm, y+bh-20.5*mm, f"{battery:.2f} kWh Speicher")
    else:
        c.drawCentredString(x+26*mm, y+bh-20.5*mm, "ohne Speicher")
    c.setFillColor(color); c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(x+26*mm, y+4*mm, f"{fmt(cost)} EUR")


def draw_table(c, x, y, configs, labels, colors):
    rows = [
        ("Anlagenleistung", [f"{cfg['kwp']:.2f} kWp" for cfg in configs], False),
        ("Speicher", [f"{cfg['battery']:.2f} kWh" if cfg['battery'] > 0 else "\u2013" for cfg in configs], False),
        ("Jahresertrag (DC)", [f"{fmt(cfg['gen_dc'])} kWh" for cfg in configs], False),
        ("Eigenverbrauch", [f"{fmt(cfg['self_ac'])} kWh" for cfg in configs], True),
        ("Autarkiegrad", [f"{cfg['autarky']}%" for cfg in configs], True),
        ("Netzeinspeisung", [f"{fmt(cfg['feed_ac'])} kWh" for cfg in configs], False),
        ("Abregelung (Verlust)", [f"{fmt(cfg['curt_dc'])} kWh" for cfg in configs], False),
        ("Restbezug Netz", [f"{fmt(cfg['grid_ac'])} kWh" for cfg in configs], False),
        ("Einspeiseverg\xfctung", [f"{cfg['feed_in_tariff']*100:.2f} ct/kWh" if cfg['feed_in_tariff'] > 0 else "\u2013" for cfg in configs], False),
        ("SEP", None, False),
        ("Investitionskosten", [f"{fmt(cfg['cost'])} EUR" for cfg in configs], False),
        ("Amortisationszeit", [f"{cfg['amort']} Jahre" if cfg['amort'] else "> 25 J." for cfg in configs], False),
        ("Ersparnis \xd8/Jahr (25 J.)", [f"{fmt(cfg['avg_savings_25'])} EUR" for cfg in configs], True),
        ("Gewinn 25 Jahre", [f"+{fmt(cfg['profit_25'])} EUR" for cfg in configs], True),
    ]
    col_w = [48*mm] + [38*mm]*len(configs)
    rh = 6*mm
    c.setFillColor(C_PRIMARY); c.rect(x, y, sum(col_w), rh+1*mm, fill=1, stroke=0)
    c.setFillColor(C_WHITE); c.setFont("Helvetica-Bold", 6.5)
    c.drawString(x+2.5*mm, y+2.5*mm, "Kennzahl")
    cx = x + col_w[0]
    for i, lb in enumerate(labels):
        c.drawCentredString(cx+col_w[i+1]/2, y+2.5*mm, lb); cx += col_w[i+1]
    vi = 0
    for label, values, bold in rows:
        if label == "SEP": continue
        ry = y - (vi+1)*rh
        if vi % 2 == 0:
            c.setFillColor(HexColor("#F9FAFB")); c.rect(x, ry, sum(col_w), rh, fill=1, stroke=0)
        if label == "Investitionskosten":
            c.setStrokeColor(C_PRIMARY); c.setLineWidth(0.4)
            c.line(x, ry+rh, x+sum(col_w), ry+rh)
        c.setFillColor(C_DARK); c.setFont("Helvetica-Bold" if bold else "Helvetica", 6.5)
        c.drawString(x+2.5*mm, ry+1.8*mm, label)
        cx = x + col_w[0]
        for i, val in enumerate(values):
            c.setFillColor(colors[i] if bold else C_DARK)
            c.setFont("Helvetica-Bold" if bold else "Helvetica", 6.5)
            c.drawCentredString(cx+col_w[i+1]/2, ry+1.8*mm, val); cx += col_w[i+1]
        vi += 1
    th = (vi+1)*rh
    c.setStrokeColor(HexColor("#D1D5DB")); c.setLineWidth(0.4)
    c.rect(x, y-th+rh, sum(col_w), th, fill=0, stroke=1)
    return y - th + rh


def draw_bars(c, x, y, w, h, configs, labels, colors):
    # Monthly consumption (same for all configs) = self_ac + grid_ac
    consumption = [configs[0]['monthly'][mi]['self_ac'] + configs[0]['monthly'][mi]['grid_ac'] for mi in range(12)]
    max_self = max(max(d['self_ac'] for d in cfg['monthly']) for cfg in configs)
    max_val = max(max(consumption), max_self) * 1.15
    n_bars = len(configs) + 1  # +1 for consumption bar
    gw = w/12; bw = gw/n_bars
    C_CONSUMPTION = HexColor("#F5A623")  # gold/orange
    c.setStrokeColor(HexColor("#E5E7EB")); c.setLineWidth(0.2)
    for f in [0, 0.25, 0.5, 0.75, 1.0]:
        gy = y+f*h; c.line(x, gy, x+w, gy)
        c.setFillColor(C_GRAY); c.setFont("Helvetica", 4.5)
        c.drawRightString(x-1.5*mm, gy-1, f"{f*max_val:.0f}")
    for mi in range(12):
        gx = x+mi*gw
        c.setFillColor(C_GRAY); c.setFont("Helvetica", 5)
        c.drawCentredString(gx+gw/2, y-3.5*mm, MONTH_NAMES[mi])
        # Consumption bar first (leftmost)
        con_val = consumption[mi]
        con_h = (con_val/max_val)*h if max_val > 0 else 0
        bx_con = gx + bw*0.15
        c.setFillColor(C_CONSUMPTION)
        if con_h > 0: c.rect(bx_con, y, bw*0.75, con_h, fill=1, stroke=0)
        # Then config bars
        for ci, cfg in enumerate(configs):
            val = cfg['monthly'][mi]['self_ac']
            bh_bar = (val/max_val)*h if max_val > 0 else 0
            bx = gx+(ci+1)*bw+bw*0.15
            c.setFillColor(colors[ci])
            if bh_bar > 0: c.rect(bx, y, bw*0.75, bh_bar, fill=1, stroke=0)
    # Legend
    ly = y-8*mm; lx = x
    # Consumption legend entry first
    c.setFillColor(C_CONSUMPTION); c.rect(lx, ly, 3*mm, 2.5*mm, fill=1, stroke=0)
    c.setFillColor(C_GRAY); c.setFont("Helvetica", 6)
    c.drawString(lx+4*mm, ly+0.3*mm, "Verbrauch")
    lx += c.stringWidth("Verbrauch", "Helvetica", 6)+10*mm
    for i in range(len(configs)):
        c.setFillColor(colors[i]); c.rect(lx, ly, 3*mm, 2.5*mm, fill=1, stroke=0)
        c.setFillColor(C_GRAY); c.setFont("Helvetica", 6)
        c.drawString(lx+4*mm, ly+0.3*mm, labels[i])
        lx += c.stringWidth(labels[i], "Helvetica", 6)+10*mm


def draw_amort(c, x, y, w, h, configs, labels, colors):
    c.saveState()
    max_cum = max(cfg["yearly"][-1]["cum"] for cfg in configs)
    max_cost = max(cfg["cost"] for cfg in configs)
    scale = max(max_cum, max_cost)*1.1
    rrect(c, x-4*mm, y-6*mm, w+8*mm, h+18*mm, 3*mm, C_WHITE, HexColor("#D1D5DB"))
    c.setFillColor(C_DARK); c.setFont("Helvetica-Bold", 8)
    c.drawString(x, y+h+7*mm, "Kumulative Ersparnis vs. Investition")
    c.setStrokeColor(HexColor("#E5E7EB")); c.setLineWidth(0.2)
    for f in [0, 0.25, 0.5, 0.75, 1.0]:
        gy = y+f*h; c.line(x, gy, x+w, gy)
        c.setFillColor(C_GRAY); c.setFont("Helvetica", 5)
        c.drawRightString(x-2*mm, gy-1.5, f"{f*scale/1000:.0f}k")
    for yr in [1,5,10,15,20,25]:
        px = x+((yr-1)/24)*w; c.setFillColor(C_GRAY); c.setFont("Helvetica", 5)
        c.drawCentredString(px, y-3.5*mm, f"J{yr}")
    for i, cfg in enumerate(configs):
        cy = y+(cfg["cost"]/scale)*h
        c.setStrokeColor(colors[i]); c.setLineWidth(0.4); c.setDash(2,2)
        c.line(x, cy, x+w, cy); c.setDash()
    for i, cfg in enumerate(configs):
        c.setStrokeColor(colors[i]); c.setLineWidth(1.5)
        p = c.beginPath()
        for j, yd in enumerate(cfg["yearly"]):
            px = x+(j/24)*w; py = y+(yd["cum"]/scale)*h
            if j == 0: p.moveTo(px, py)
            else: p.lineTo(px, py)
        c.drawPath(p)
        if cfg["amort"]:
            ai = cfg["amort"]-1
            cum_at = cfg["yearly"][ai]["cum"]
            cum_b = cfg["yearly"][ai-1]["cum"] if ai > 0 else 0
            frac = (cfg["cost"]-cum_b)/(cum_at-cum_b) if cum_at != cum_b else 0.5
            ex = (ai-1+frac) if ai > 0 else frac
            ax = x+(ex/24)*w; ay = y+(cfg["cost"]/scale)*h
            c.setFillColor(colors[i]); c.circle(ax, ay, 2.5, fill=1, stroke=0)
            c.setStrokeColor(C_WHITE); c.setLineWidth(1)
            c.circle(ax, ay, 2.5, fill=0, stroke=1)
    lx = x; ly = y-8*mm
    for i, lb in enumerate(labels):
        c.setStrokeColor(colors[i]); c.setLineWidth(1.5)
        c.line(lx, ly+1, lx+4*mm, ly+1)
        c.setFillColor(C_GRAY); c.setFont("Helvetica", 5.5)
        c.drawString(lx+5.5*mm, ly, lb)
        lx += c.stringWidth(lb, "Helvetica", 5.5)+10*mm
    c.restoreState()


# ═══════════════════════════════════════════════════════════════════════

def generate_report(customer, montage="Schraegdach", report_type="dach", electricity_price=0.36, max_modules=None, output_path=None):
    """
    customer: dict with name, street, city, consumption, orientation
    montage: "Schraegdach" | "Flachdach" | "Balkon"
    report_type: "dach" | "balkon"
    electricity_price: EUR/kWh (default 0.36)
    max_modules: max number of modules that fit on the roof (optional)
    output_path: path for PDF output (default: /home/claude/solar_bericht_v5.pdf)
    """
    price_increase = 0.035
    bifacial_gain = BIFACIAL[montage]

    # Parse salutation from name (e.g. "Frau Karin Kuhl" → anrede="Frau", display name="Karin Kuhl")
    raw_name = customer["name"].strip()
    if raw_name.lower().startswith("frau "):
        anrede = "Sehr geehrte Frau"
        display_name = raw_name[5:].strip()
    elif raw_name.lower().startswith("herr "):
        anrede = "Sehr geehrter Herr"
        display_name = raw_name[5:].strip()
    else:
        anrede = "Sehr geehrte/r Herr/Frau"
        display_name = raw_name
    customer_lastname = display_name.split()[-1]

    # Select catalog & packages
    if report_type == "balkon":
        catalog = CATALOG_BALKON
        selected_ids = [c["id"] for c in catalog]
    else:
        catalog = CATALOG_DACH
        selected_ids = select_packages(customer["consumption"], max_modules=max_modules)

    # Simulate selected configs
    configs = []
    for pkg in catalog:
        if pkg["id"] not in selected_ids:
            continue
        r = simulate(
            module_count=pkg["modules"], module_wp=445,
            battery_kwh=pkg["battery"], max_inverter_w=800,
            annual_consumption=customer["consumption"],
            electricity_price=electricity_price,
            feed_in_tariff=pkg["fit"],
            system_cost=pkg["cost"],
            bifacial_gain=bifacial_gain,
            price_increase_rate=price_increase,
        )
        r["label"] = pkg["label"]
        r["battery"] = pkg["battery"]
        configs.append(r)

    labels = [c["label"] for c in configs]
    colors = [C_ACCENT_DARK, C_PRIMARY, C_BLUE][:len(configs)]

    # Recommendations: single recommendation
    # Default: P/L winner (best profit/cost ratio)
    # Upgrade to larger package only if it has ≥2.500€ MORE profit than P/L winner
    pl_scores = [cfg["profit_25"]/cfg["cost"] if cfg["profit_25"] > 0 else 0 for cfg in configs]
    pl_idx = pl_scores.index(max(pl_scores))
    profits = [cfg["profit_25"] for cfg in configs]

    rec_idx = pl_idx
    for i in range(len(configs) - 1, -1, -1):
        if i != pl_idx and (profits[i] - profits[pl_idx]) >= 2500:
            rec_idx = i
            break

    # Speicher-Downgrade: wenn empfohlenes Paket ein "Speicher-Geschwister" hat
    # (gleiche Modulzahl, kleinerer Speicher) und der Mehrgewinn <1.000€ ist,
    # dann das kleinere Speicher-Paket empfehlen (Speichertausch nach 10-15 J. wahrscheinlich)
    rec_cfg = configs[rec_idx]
    for i, cfg in enumerate(configs):
        if i != rec_idx and cfg["modules"] == rec_cfg["modules"] and cfg["battery"] < rec_cfg["battery"]:
            if (profits[rec_idx] - profits[i]) < 1000:
                rec_idx = i
                break

    badges = {rec_idx: "UNSERE EMPFEHLUNG"}

    montage_labels = {"Schraegdach": "Schr\xe4gdach", "Flachdach": "Flachdach/Aufst\xe4nderung", "Balkon": "Balkon"}
    ml = montage_labels[montage]

    # Speicher-Erweiterungshinweis
    has_4mod = any(c["modules"] == 4 for c in configs)
    has_6plus = any(c["modules"] >= 6 for c in configs)
    speicher_hint_parts = []
    if has_4mod: speicher_hint_parts.append("4-Modul = 1,92 kWh-Bl\xf6cke")
    if has_6plus: speicher_hint_parts.append("6/8-Modul = 2,7 kWh-Bl\xf6cke")
    speicher_hint = "Speicher erweiterbar: " + "  \xb7  ".join(speicher_hint_parts) if speicher_hint_parts else ""

    # BKW/EEG hint
    has_bkw = any(c["modules"] <= 4 for c in configs)
    has_eeg = any(c["modules"] > 4 for c in configs)
    vergutung_parts = []
    if has_bkw: vergutung_parts.append("BKW (\u22644 Module): keine Einspeiseverg\xfctung")
    if has_eeg: vergutung_parts.append(f"Registrierte PV (>4 Module): {configs[-1]['feed_in_tariff']*100:.2f} ct/kWh EEG")
    vergutung_hint = "  \xb7  ".join(vergutung_parts)

    # ─── PDF ─────────────────────────────────────────────────────────
    out = output_path or "/home/claude/solar_bericht_v5.pdf"
    pdf = canvas.Canvas(out, pagesize=A4)
    tp = 3

    # ═══ PAGE 1 ═══
    draw_header(pdf, 1, tp); draw_footer(pdf)
    y = H - 42*mm
    pdf.setFillColor(C_DARK); pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(20*mm, y, "Ihr pers\xf6nlicher"); y -= 9*mm
    pdf.setFillColor(C_PRIMARY); pdf.drawString(20*mm, y, "Solar-Empfehlungsbericht")
    y -= 5*mm; pdf.setFillColor(C_ACCENT); pdf.rect(20*mm, y, 40*mm, 1*mm, fill=1, stroke=0)
    y -= 8*mm; pdf.setFillColor(C_GRAY); pdf.setFont("Helvetica", 8)
    pdf.drawString(20*mm, y, "Erstellt am 14. April 2026  \xb7  Berichts-Nr. MSF-2026-0414")

    # Customer box
    y -= 12*mm; bh = 26*mm
    rrect(pdf, 20*mm, y-bh, W-40*mm, bh, 3*mm, C_BG_LIGHT, C_PRIMARY)
    pdf.setFillColor(C_PRIMARY); pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(26*mm, y-5*mm, "Objektdaten")
    pdf.setFillColor(C_DARK); pdf.setFont("Helvetica", 8)
    pdf.drawString(26*mm, y-12*mm, f"Eigent\xfcmer:  {display_name}")
    pdf.drawString(26*mm, y-18*mm, f"Adresse:  {customer['street']}, {customer['city']}")
    pdf.drawString(110*mm, y-12*mm, f"Jahresverbrauch:  {fmt(customer['consumption'])} kWh")
    pdf.drawString(110*mm, y-18*mm, f"Dachausrichtung:  {customer['orientation']}")
    pdf.drawString(26*mm, y-24*mm, f"Montage: {ml}  \xb7  Bifazialmodule (+{(bifacial_gain-1)*100:.0f}%)")
    pdf.drawString(110*mm, y-24*mm, f"Strompreis: {electricity_price:.2f} EUR/kWh")

    # Section: packages
    y -= bh + 10*mm
    pdf.setFillColor(C_DARK); pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(20*mm, y, f"Ihre Paketauswahl ({len(configs)} von {len(catalog)} Optionen)"); y -= 4*mm
    pdf.setFillColor(C_GRAY); pdf.setFont("Helvetica", 7.5)
    pdf.drawString(20*mm, y, "800 W Microinverter (Steckdoseneinspeisung)  \xb7  Smart-Meter-Steuerung"); y -= 4*mm
    pdf.setFont("Helvetica", 7)
    pdf.drawString(20*mm, y, vergutung_hint); y -= 4*mm
    if speicher_hint:
        pdf.drawString(20*mm, y, speicher_hint); y -= 4*mm

    # Badges
    y -= 38*mm; bx = 20*mm
    for i, cfg in enumerate(configs):
        draw_badge(pdf, bx, y, labels[i], cfg["modules"], cfg["battery"], cfg["cost"],
                   colors[i], badge_text=badges.get(i))
        bx += 56*mm

    # Intro
    y -= 16*mm; pdf.setFillColor(C_DARK); pdf.setFont("Helvetica", 8)
    for line in [
        f"{anrede} {customer_lastname},",
        "",
        f"f\xfcr Ihren Jahresverbrauch von {fmt(customer['consumption'])} kWh und {customer['orientation']}-",
        f"Ausrichtung haben wir die passenden Konfigurationen stundengenau simuliert (8.760 h/a).",
        f"Alle Systeme nutzen einen 800-W-Microinverter mit Smart-Meter-Steuerung",
        f"und Bifazialmodule (+{(bifacial_gain-1)*100:.0f}% Mehrertrag bei {ml}).",
        "",
        "Verlustannahmen: 1% Kabelverluste, 2,5% Verschmutzung (PR 96,5%).",
        f"Strompreissteigerung: {price_increase*100:.1f}% p.a. (historischer Durchschnitt DE, 2010\u20132024).",
    ]:
        pdf.drawString(20*mm, y, line); y -= 4*mm

    # Insight box
    y -= 4*mm; ih = 30*mm
    rrect(pdf, 20*mm, y-ih, W-40*mm, ih, 3*mm, C_BG_ACCENT, C_ACCENT_DARK)
    pdf.setFillColor(C_PRIMARY); pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(26*mm, y-7*mm, "Auf einen Blick")
    pdf.setFillColor(C_DARK); pdf.setFont("Helvetica", 8)
    no_pv = customer["consumption"] * electricity_price
    rec = configs[rec_idx]
    pdf.drawString(26*mm, y-15*mm, f"Ohne Solar: ca. {fmt(no_pv)} EUR/Jahr Stromkosten.")
    pdf.drawString(26*mm, y-22*mm, f"Mit {labels[rec_idx]}: \xd8 {fmt(rec['avg_savings_25'])} EUR Ersparnis/Jahr,")
    pdf.drawString(26*mm, y-28*mm, f"Amortisation in {rec['amort']} Jahren, +{fmt(rec['profit_25'])} EUR Gewinn in 25 Jahren.")
    pdf.showPage()

    # ═══ PAGE 2 ═══
    draw_header(pdf, 2, tp); draw_footer(pdf)
    y = H - 40*mm
    pdf.setFillColor(C_DARK); pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(20*mm, y, "Detailvergleich"); y -= 6*mm
    pdf.setFillColor(C_GRAY); pdf.setFont("Helvetica", 7.5)
    pdf.drawString(20*mm, y, "Stundenbasiert, mit Klar-/Bew\xf6lkt-Tagesverteilung und 800-W-Inverter-Limit")
    y -= 10*mm
    tbl_bot = draw_table(pdf, 20*mm, y, configs, labels, colors)

    y = tbl_bot - 6*mm; eh = 22*mm
    rrect(pdf, 20*mm, y-eh, W-40*mm, eh, 2*mm, C_BG_LIGHT, C_PRIMARY)
    pdf.setFillColor(C_PRIMARY); pdf.setFont("Helvetica-Bold", 7)
    pdf.drawString(26*mm, y-5*mm, "So lesen Sie die Zahlen")
    pdf.setFillColor(C_DARK); pdf.setFont("Helvetica", 6.5)
    pdf.drawString(26*mm, y-10*mm, "Eigenverbrauch = Solarstrom, der direkt Ihren Verbrauch deckt (max. 800 W Inverter-Ausgang).")
    pdf.drawString(26*mm, y-15*mm, f"Autarkie = Anteil Ihres Gesamtverbrauchs, der durch die Anlage gedeckt wird.")
    pdf.drawString(26*mm, y-20*mm, "Abregelung = Solarstrom, der bei vollem Speicher \xfcber 800 W hinaus verloren geht.")
    y -= eh

    y -= 8*mm; ch = 42*mm
    pdf.setFillColor(C_DARK); pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(20*mm, y, "Monatlicher Verbrauch vs. Eigenverbrauch (kWh)")
    cb = y - 5*mm - ch
    draw_bars(pdf, 30*mm, cb, W-50*mm, ch, configs, labels, colors)
    y = cb - 12*mm

    curt_cfgs = [(i, cfg) for i, cfg in enumerate(configs) if cfg['curt_dc'] > 5]
    if curt_cfgs:
        nh = 10*mm + len(curt_cfgs)*5*mm
        rrect(pdf, 20*mm, y-nh, W-40*mm, nh, 2*mm, HexColor("#FEF2F2"), C_RED)
        pdf.setFillColor(C_RED); pdf.setFont("Helvetica-Bold", 7)
        pdf.drawString(26*mm, y-5*mm, "Abregelung durch 800-W-Inverter-Grenze")
        pdf.setFillColor(C_DARK); pdf.setFont("Helvetica", 6.5)
        for j, (i, cfg) in enumerate(curt_cfgs):
            pdf.drawString(26*mm, y-11*mm-j*5*mm,
                f"{labels[i]}: ca. {fmt(cfg['curt_dc'])} kWh/Jahr abgeregelt"
                f" ({cfg['curt_dc']/cfg['gen_dc']*100:.1f}% der Erzeugung)")
    pdf.showPage()

    # ═══ PAGE 3 ═══
    draw_header(pdf, 3, tp); draw_footer(pdf)
    y = H - 40*mm
    pdf.setFillColor(C_DARK); pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(20*mm, y, "Wirtschaftlichkeit & Empfehlung"); y -= 10*mm
    draw_amort(pdf, 30*mm, y-55*mm, W-52*mm, 50*mm, configs, labels, colors)

    y -= 74*mm; nc = len(configs); bw = (W-40*mm-(nc-1)*4*mm)/nc
    for i, cfg in enumerate(configs):
        bx = 20*mm+i*(bw+4*mm); bh_box = 28*mm
        rrect(pdf, bx, y-bh_box, bw, bh_box, 3*mm, C_BG_ACCENT if i in badges else C_WHITE, colors[i])
        pdf.setFillColor(colors[i]); pdf.setFont("Helvetica-Bold", 7.5)
        pdf.drawCentredString(bx+bw/2, y-5*mm, labels[i])
        if i in badges:
            pdf.setFont("Helvetica-Bold", 5)
            pdf.drawCentredString(bx+bw/2, y-10*mm, badges[i])
        pdf.setFillColor(C_DARK); pdf.setFont("Helvetica", 6.5)
        pdf.drawCentredString(bx+bw/2, y-15*mm, f"Amortisation: {cfg['amort']} J." if cfg['amort'] else "> 25 J.")
        pdf.setFillColor(colors[i]); pdf.setFont("Helvetica-Bold", 12)
        pdf.drawCentredString(bx+bw/2, y-21*mm, f"+{fmt(cfg['profit_25'])} EUR")
        pdf.setFillColor(C_GRAY); pdf.setFont("Helvetica", 5.5)
        pdf.drawCentredString(bx+bw/2, y-25.5*mm, "Gewinn in 25 Jahren")

    y -= 40*mm; rh = 34*mm
    rrect(pdf, 20*mm, y-rh, W-40*mm, rh, 4*mm, C_PRIMARY)
    pdf.setFillColor(C_WHITE); pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(28*mm, y-8*mm, "Unsere Empfehlung"); ty = y-17*mm
    pc = configs[rec_idx]
    pdf.setFillColor(C_ACCENT); pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(28*mm, ty, f"{labels[rec_idx]}"); ty -= 5*mm
    pdf.setFillColor(C_WHITE); pdf.setFont("Helvetica", 7.5)
    pdf.drawString(28*mm, ty, f"{fmt(pc['cost'])} EUR Invest, +{fmt(pc['profit_25'])} EUR Gewinn in 25 J."); ty -= 4.5*mm
    pdf.drawString(28*mm, ty, f"Amortisation {pc['amort']} J., {pc['autarky']}% Autarkie, \xd8 {fmt(pc['avg_savings_25'])} EUR/J. Ersparnis.")

    # ── Was kostet Nicht-Handeln? ──
    y -= rh+6*mm; opp_h = 34*mm
    # Calculate 25-year electricity cost without PV
    cost_no_pv_25 = sum(
        customer["consumption"] * electricity_price * (1 + price_increase) ** (yr - 1)
        for yr in range(1, 26)
    )
    # With PV (P/L winner): remaining grid cost + invest - cumulative savings already captured in cum_25
    cost_with_pv_25 = cost_no_pv_25 - pc["cum_25"] + pc["cost"]
    saved_total = cost_no_pv_25 - cost_with_pv_25

    rrect(pdf, 20*mm, y-opp_h, W-40*mm, opp_h, 4*mm, HexColor("#FFF7ED"), HexColor("#F59E0B"))
    pdf.setFillColor(C_DARK); pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(26*mm, y-7*mm, "Was kostet es, nicht zu handeln?")
    pdf.setFillColor(C_DARK); pdf.setFont("Helvetica", 7.5)
    pdf.drawString(26*mm, y-14*mm,
        f"Ohne Solaranlage zahlen Sie in 25 Jahren voraussichtlich {fmt(round(cost_no_pv_25))} EUR Stromkosten")
    pdf.drawString(26*mm, y-19.5*mm,
        f"(bei {price_increase*100:.1f}% j\xe4hrlicher Strompreissteigerung, historischer Durchschnitt DE).")
    pdf.setFillColor(C_PRIMARY); pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(26*mm, y-27*mm,
        f"Mit {labels[rec_idx]} sparen Sie {fmt(round(pc['cum_25']))} EUR an Stromkosten \u2014 bei nur {fmt(pc['cost'])} EUR Investition.")
    pdf.setFillColor(C_GRAY); pdf.setFont("Helvetica", 6.5)
    pdf.drawString(26*mm, y-32*mm,
        f"Jedes Jahr ohne PV kostet Sie im Durchschnitt {fmt(round(cost_no_pv_25/25))} EUR an Ihren Stromanbieter.")

    y -= opp_h+6*mm; cta_h = 26*mm
    rrect(pdf, 20*mm, y-cta_h, W-40*mm, cta_h, 4*mm, C_BG_ACCENT, C_ACCENT_DARK)
    pdf.setFillColor(C_DARK); pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(28*mm, y-8*mm, "Bereit f\xfcr Ihre Solaranlage?")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(28*mm, y-15*mm, "Kostenloses Beratungsgespr\xe4ch:")
    pdf.drawString(28*mm, y-22*mm, "kontakt@mysolarfuture.de  \xb7  www.mysolarfuture.de")

    y -= cta_h+6*mm; pdf.setFillColor(C_GRAY); pdf.setFont("Helvetica", 5)
    for line in [
        f"Simulation, keine Ertragsprognose. Bifazialmodule, PR 96,5% (1% Kabel, 2,5% Verschmutzung). Abweichungen m\xf6glich.",
        f"Strompreissteigerung {price_increase*100:.1f}% p.a. = historischer Durchschnitt DE (2010\u20132024). EEG-Verg\xfctung f\xfcr registrierte Anlagen >2 kWp.",
        "Preise inkl. MwSt. (0% PV gem. UStG). Freibleibend.",
    ]:
        pdf.drawString(20*mm, y, line); y -= 3*mm

    pdf.save()

    # ─── DEBUG ───────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"SOLAR-BERICHT v5 \u2014 {customer['name']}, {customer['consumption']} kWh, {ml}")
    print(f"Bifazial +{(bifacial_gain-1)*100:.0f}%, PR 96,5%, FIT: {vergutung_hint}")
    print(f"Ausgew\xe4hlt: {', '.join(labels)}")
    print(f"{'='*70}")
    for i, cfg in enumerate(configs):
        print(f"\n{labels[i]} ({cfg['modules']}\xd7445Wp + {cfg['battery']:.2f} kWh, {fmt(cfg['cost'])} EUR)")
        print(f"  Erzeugung DC:    {cfg['gen_dc']} kWh")
        print(f"  Eigenverbrauch:  {cfg['self_ac']} kWh  |  Autarkie: {cfg['autarky']}%")
        print(f"  Einspeisung:     {cfg['feed_ac']} kWh  |  Abregelung: {cfg['curt_dc']} kWh")
        print(f"  Netzbezug:       {cfg['grid_ac']} kWh")
        bal = cfg['self_ac']+cfg['grid_ac']
        print(f"  Bilanz:          {bal} vs {customer['consumption']}  {'OK' if abs(bal-customer['consumption'])<5 else 'FAIL'}")
        print(f"  Ersparnis \xd8/J:  {cfg['avg_savings_25']} EUR  |  Amort: {cfg['amort']} J.  |  Gewinn 25J: +{fmt(cfg['profit_25'])} EUR")
    print(f"\n  Empfehlung:      {labels[rec_idx]}")
    if rec_idx != pl_idx:
        print(f"  (Upgrade von {labels[pl_idx]}: +{fmt(profits[rec_idx]-profits[pl_idx])} EUR Mehrersparnis)")
    return out


# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # --- Test: Dachanlage, >2500 kWh ---
    customer_hott = {
        "name": "Maurice Hott", "street": "Fichtenstr. 20",
        "city": "27751 Delmenhorst", "consumption": 4000, "orientation": "S\xfcd",
    }
    generate_report(customer_hott, montage="Schraegdach", report_type="dach")

    # --- Quick test: what would ≤2500 kWh select? ---
    print("\n\n--- SELECTION TEST ---")
    for cons in [1500, 2000, 2500, 3000, 4000, 5000]:
        sel = select_packages(cons)
        print(f"  {cons:5d} kWh \u2192 {sel}")
