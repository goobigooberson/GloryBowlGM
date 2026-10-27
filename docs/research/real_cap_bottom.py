# docs/research/real_cap_bottom.py
# Who sits at the bottom of the cap-room table the day after the league year opens (Oct 26;
# Blake: "how hard AI teams commit money ... so near-broke teams match real").
# Data: OverTheCap's "Cap Space" page as saved by the Internet Archive the day after each new
# league year opened (March 17, 2022; March 17, 2023; March 14, 2024; March 13, 2025), with each
# team's dead money; last season's wins and whether it made the playoffs, entered by hand from
# the final standings. The same days as tools/free_agency_check.py's REAL_FA_DAY1 (room only); for 2023
# this is a later capture of the same day (7:07 pm), so a few teams' room differs by $1-2M from it.
# Prints the bottom 8 each year, room / record / dead money by rank group, how often playoff teams
# end up under 2% of the cap, and how often a bottom-8 team is there again the next year.
#   python docs/research/real_cap_bottom.py
import statistics as st

# team: (cap space $M, dead money $M)
DAY1 = {
    2022: (208.2, """Colts 44.26 6.81|Seahawks 39.66 40.63|Jets 37.31 1.55|Raiders 34.63 23.32|Panthers 32.14 22.09|Bears 29.42 45.18|Cowboys 26.59 17.72|Dolphins 24.75 1.66|Chargers 22.70 3.66|Steelers 21.03 24.04|Commanders 19.84 2.45|Falcons 17.43 21.57|Browns 16.26 10.06|Eagles 15.66 36.45|Jaguars 13.98 23.06|Ravens 13.97 7.35|Bengals 13.34 3.48|Patriots 13.09 8.96|Broncos 13.01 14.93|Texans 12.02 35.58|Lions 12.01 8.17|49ers 9.16 5.17|Bills 8.33 9.90|Cardinals 6.62 5.90|Rams 0.90 2.36|Saints 0.77 29.38|Titans 0.66 8.97|Vikings -3.58 22.09|Packers -8.16 24.62|Giants -9.37 8.02|Buccaneers -9.58 19.43|Chiefs -10.68 6.53"""),
    2023: (224.8, """Bears 44.88 22.97|Falcons 34.64 16.59|Packers 24.41 16.81|Cardinals 23.32 11.72|Raiders 22.67 30.06|Cowboys 21.34 8.88|Colts 20.53 23.24|Patriots 20.43 16.58|Steelers 19.86 11.28|Bengals 19.30 0.59|Saints 18.67 22.86|Lions 18.30 10.26|Chargers 17.86 2.19|Panthers 17.55 50.91|Seahawks 17.44 16.14|Titans 15.47 36.81|Browns 14.73 10.37|Chiefs 14.13 7.77|Texans 13.89 8.00|Jets 13.60 6.12|Dolphins 12.12 3.50|Broncos 11.07 7.59|Bills 9.15 4.91|49ers 9.05 17.09|Commanders 8.50 18.99|Rams 8.41 52.77|Giants 7.89 22.74|Ravens 7.86 10.63|Jaguars 5.28 5.41|Eagles 3.96 54.73|Vikings -1.15 27.02|Buccaneers -1.43 70.61"""),
    2024: (255.4, """Titans 72.07 31.84|Commanders 67.96 27.26|Patriots 57.16 21.50|Bears 56.31 10.54|Bengals 45.69 6.53|Cardinals 40.59 14.15|Eagles 39.97 16.38|Seahawks 34.16 36.09|Colts 31.91 8.36|Lions 29.23 23.05|Broncos 26.81 14.07|Packers 25.97 46.56|Texans 21.03 23.78|Vikings 18.89 57.37|Panthers 17.75 46.05|Steelers 17.33 20.68|Chiefs 15.32 5.90|Saints 15.10 24.61|Raiders 12.85 37.79|Jets 11.91 34.54|Ravens 10.82 12.09|Rams 9.85 4.15|Falcons 4.70 5.52|Giants 3.56 19.04|Buccaneers 3.44 35.96|Jaguars 3.04 17.91|Cowboys 2.24 14.77|Browns 1.21 15.64|Dolphins 1.07 22.37|49ers -1.78 9.15|Bills -2.21 23.89|Chargers -7.81 39.77"""),
    2025: (279.2, """Patriots 100.90 13.91|Chargers 83.01 24.46|Cardinals 70.25 7.40|Titans 66.10 24.65|Seahawks 60.81 67.07|Lions 55.25 18.80|Cowboys 53.61 20.73|Vikings 48.18 10.73|Raiders 47.50 44.22|Steelers 47.28 3.58|Jaguars 46.42 52.94|49ers 43.69 77.72|Panthers 35.10 10.69|Bengals 34.54 6.61|Jets 33.76 37.18|Commanders 32.76 14.13|Packers 32.15 18.31|Giants 32.08 27.30|Chiefs 28.41 13.06|Eagles 27.52 55.61|Broncos 26.14 33.45|Rams 23.85 25.72|Bears 22.60 4.05|Saints 16.53 52.66|Browns 13.77 54.54|Colts 11.82 3.32|Buccaneers 9.93 33.55|Texans 6.88 38.37|Falcons 6.33 7.58|Bills 6.24 29.42|Ravens 0.76 20.39|Dolphins -10.30 27.85"""),
}
# Last season's record (wins, made the playoffs) for the league year's teams.
PRIOR = {
    2022: "Titans 12 1|Packers 13 1|Buccaneers 13 1|Chiefs 12 1|Rams 12 1|Bengals 10 1|Bills 11 1|Cowboys 12 1|Raiders 10 1|Patriots 10 1|Cardinals 11 1|49ers 10 1|Eagles 9 1|Steelers 9 1|"
          "Colts 9 0|Chargers 9 0|Dolphins 9 0|Saints 9 0|Browns 8 0|Ravens 8 0|Vikings 8 0|Broncos 7 0|Commanders 7 0|Falcons 7 0|Seahawks 7 0|Panthers 5 0|Bears 6 0|Jets 4 0|Giants 4 0|Texans 4 0|Lions 3 0|Jaguars 3 0",
    2023: "Chiefs 14 1|Eagles 14 1|Bills 13 1|Vikings 13 1|49ers 13 1|Bengals 12 1|Cowboys 12 1|Chargers 10 1|Ravens 10 1|Giants 9 1|Dolphins 9 1|Jaguars 9 1|Seahawks 9 1|Buccaneers 8 1|"
          "Lions 9 0|Steelers 9 0|Commanders 8 0|Packers 8 0|Patriots 8 0|Jets 7 0|Titans 7 0|Browns 7 0|Falcons 7 0|Panthers 7 0|Saints 7 0|Raiders 6 0|Rams 5 0|Broncos 5 0|Cardinals 4 0|Colts 4 0|Texans 3 0|Bears 3 0",
    2024: "Ravens 13 1|49ers 12 1|Cowboys 12 1|Lions 12 1|Bills 11 1|Chiefs 11 1|Browns 11 1|Dolphins 11 1|Eagles 11 1|Steelers 10 1|Texans 10 1|Buccaneers 9 1|Rams 10 1|Packers 9 1|"
          "Jaguars 9 0|Colts 9 0|Seahawks 9 0|Bengals 9 0|Saints 9 0|Vikings 7 0|Broncos 8 0|Raiders 8 0|Falcons 7 0|Jets 7 0|Bears 7 0|Giants 6 0|Titans 6 0|Chargers 5 0|Patriots 4 0|Commanders 4 0|Cardinals 4 0|Panthers 2 0",
    2025: "Chiefs 15 1|Lions 15 1|Eagles 14 1|Vikings 14 1|Bills 13 1|Ravens 12 1|Commanders 12 1|Packers 11 1|Chargers 11 1|Steelers 10 1|Texans 10 1|Rams 10 1|Buccaneers 10 1|Broncos 10 1|"
          "Bengals 9 0|Seahawks 10 0|Falcons 8 0|Cardinals 8 0|Dolphins 8 0|Colts 8 0|49ers 6 0|Cowboys 7 0|Jets 5 0|Saints 5 0|Bears 5 0|Jaguars 4 0|Panthers 5 0|Patriots 4 0|Giants 3 0|Titans 3 0|Raiders 4 0|Browns 3 0",
}

rows = []
for y, (cap, txt) in DAY1.items():
    prior = {a.split()[0]: (int(a.split()[1]), int(a.split()[2])) for a in PRIOR[y].split("|")}
    assert len(prior) == 32, (y, len(prior))
    teams = []
    for a in txt.split("|"):
        n, room, dead = a.split()
        teams.append((n, float(room) / cap, float(dead) / cap))
    assert len(teams) == 32
    teams.sort(key=lambda x: -x[1])
    for rank, (n, r, d) in enumerate(teams):
        assert n in prior, n
        rows.append(dict(y=y, team=n, rank=rank + 1, room=r, dead=d, wins=prior[n][0], po=prior[n][1]))

for y in DAY1:
    b = [r for r in rows if r["y"] == y and r["rank"] >= 25]
    print(y, "bottom 8:", ", ".join(f"{r['team']} {100*r['room']:.1f}% ({r['wins']}w{'*' if r['po'] else ''})" for r in b))

print()
for lo, hi, lab in ((1, 8, "top 8"), (9, 16, "9-16"), (17, 24, "17-24"), (25, 32, "bottom 8")):
    g = [r for r in rows if lo <= r["rank"] <= hi]
    print(f"{lab:9s} room {100*st.mean(r['room'] for r in g):5.1f}%  prior wins {st.mean(r['wins'] for r in g):4.1f}  "
          f"playoff share {st.mean(r['po'] for r in g):.2f}  dead {100*st.mean(r['dead'] for r in g):.1f}%")
u2 = [r for r in rows if r["room"] < 0.02]
print(f"\nunder 2%: {len(u2)/4:.1f} a year; playoff share {st.mean(r['po'] for r in u2):.2f}; prior wins {st.mean(r['wins'] for r in u2):.1f}; "
      f"10+ wins {st.mean(r['wins']>=10 for r in u2):.2f} (all teams {st.mean(r['wins']>=10 for r in rows):.2f})")
# Playoff teams' and others' rank distribution
for po in (1, 0):
    g = [r for r in rows if r["po"] == po]
    print(f"{'playoff' if po else 'others '} teams: in bottom 8 {st.mean(r['rank']>=25 for r in g):.2f}, under 2% {st.mean(r['room']<0.02 for r in g):.2f}, "
          f"median room {100*st.median(r['room'] for r in g):.1f}%")
# Persistence: bottom 8 one year -> next year
by = {(r["y"], r["team"]): r for r in rows}
pairs = [(by[(y, t)], by[(y + 1, t)]) for (y, t) in by if (y + 1, t) in by]
b8 = [b for a, b in pairs if a["rank"] >= 25]
print(f"bottom 8 one year -> bottom 8 next year {st.mean(b['rank']>=25 for b in b8):.2f} (chance 0.25); "
      f"under 2% -> under 2% next {st.mean(b['room']<0.02 for a,b in pairs if a['room']<0.02):.2f}")
import collections
cnt = collections.Counter(r["team"] for r in rows if r["rank"] >= 25)
print("bottom-8 appearances in 4 years:", cnt.most_common())
# room vs wins correlation
xs = [r["wins"] for r in rows]; ys = [r["room"] for r in rows]
mx, my = st.mean(xs), st.mean(ys)
corr = sum((a-mx)*(b-my) for a,b in zip(xs,ys)) / (len(xs)*st.pstdev(xs)*st.pstdev(ys))
print(f"correlation prior wins vs day-1 room {corr:.2f}")
