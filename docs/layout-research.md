# Layout research: deep without being overwhelming

Research for Blake's question: how do we lay out the game so it never feels
overwhelming, but still feels comprehensive and full of content? Nothing here
is built or decided yet. The recommendations are mine; the open questions at
the end are Blake's calls.

## The short version

1. **"Overwhelming" comes from a screen not telling you where to look, not from how
   much data the game has.** The games that got this wrong (Football Manager 26,
   Victoria 3) hid data to look simpler and players hated it. The games that are loved
   for depth (FOF, OOTP, the Bloomberg Terminal for traders) show a lot, but in layers
   and in the same place every time.
2. **Use three layers:** an *overview* (a home screen: what needs you this week),
   *browsing* (the tabs: tables you sort and filter), and *details* (pop-ups: one
   player, one game). The game already has layers 2 and 3. **Layer 1, a home screen,
   is missing**, and it's the single biggest improvement available.
3. **Give the data the screen.** Right now, in a 1600x900 window, about two-thirds of
   the Roster tab's height goes to header bands, the season bar, the tab row, the
   to-do box and filter rows before the first player. About 9 players fit on screen.
4. **12 tabs in one row is about twice what tab bars handle well** (design guides say
   5-7). Group them into about 6 hubs with sub-tabs.
5. **Pop-ups are right for "look at one thing and come back"** (player card, box
   score) and wrong for "work through many things" (a draft board, free agency).
   Football Manager learned this the hard way in 2025-26.
6. **Smaller wins:** hover explanations for every term (Crusader Kings style), saved
   table views, tiny inline charts (sparklines) for streaks and rating history,
   keyboard shortcuts, and keeping color for meaning only.

---

## 1. What I saw in the game today

I opened the "Midseason test" save (week 5, Boston) in a 1600x900 window and went
through Roster, Stats, Bitter and Depth chart.

**Stacked bars above every tab** (top to bottom):
- Green header band: game title, team picker, save status, Save, Save a copy, Main menu.
- Team banner: big "BOS", team name, conference, roster count, starters' rating.
- Season bar: week and date, record, this week's opponent, last game, Game summary,
  Watch my game, Sim week, Sim ahead.
- Tab row: 12 tabs (Roster, Contracts, Draft, Depth chart, Position counts, Schedule,
  Standings, Stats, Playoffs, Bitter, Awards, Game).

**Then each tab adds its own rows.** Roster adds a status line, a yellow "Roster to-do"
box (7 lines that week), a row of view buttons (Roster / Practice squad / Reserve lists /
Moves), a row of unit filters (All / Offense / Defense / Special teams) plus a position
menu, a key, and a practice squad toggle. The player table starts about 71% of the way
down the window, and the table scrolls inside its own short box.

**What's already good and should be kept:**
- The side panel on Roster (click a row, see the player beside the table without losing
  your place). Research below backs this exact pattern.
- The season bar's "what's happening now" idea (this week's game, Sim week). That's the
  seed of a home screen.
- Rating words plus numbers ("Very Good (84)"), labeled buttons and columns.
- Stats tab's team summary: a lot of data, but in clear boxes with headings. Dense
  and readable.
- Bitter's layout (filters left, feed center, "What's happening" right) is a familiar
  three-column pattern people already know how to read.

**What adds to the "a lot going on" feeling:**
- The same few things (team, week, record) are shown in three different bars.
- Two team pickers: one in the header (changes several tabs) and one inside Stats.
  It's easy to lose track of whose team you're looking at, and only your own team
  can be edited.
- Every tab invents its own control rows, so your eye has to re-learn each screen.
- The to-do box pushes the roster down by a different amount every week.
- Many colors at once (position colors, rating colors, injury tags, the yellow box), so
  nothing stands out as "look here first".

---

## 2. What the research says

### Football Manager 26 and 27: the biggest recent lesson
Football Manager 26 (2025) rebuilt its interface around "tiles" and "cards" that
summarized information, a top menu instead of the old sidebar, and more pop-up windows.
The stated goal was to make screens easier to read. The result: Steam reviews around 81%
negative (the two prior games were "Overwhelmingly Positive"), with complaints that
information that used to be one click away now took several, that staff overviews on
one page were gone (click each person, go back, click the next), that the Back button
jumped to unrelated screens, and that view settings kept resetting. PC Gamer said the
interface "makes my brain hurt". A reviewer also noted that off the pitch it *still*
overloaded you with information.

Football Manager 27 (out Nov 2026) is the correction. Sports Interactive's stated aims:
fewer clicks by showing more on a single screen, fuller screens instead of small tiles,
**many pop-ups replaced with full pages**, drop-down menus on the top navigation so you
can jump straight to a sub-page, choosing which page each menu opens to first, swappable
tiles, rearrangeable bookmarks, remappable keyboard shortcuts, inbox messages color-coded
by urgency, duplicate messages (several transfer offers) grouped, and scout reports
readable without opening them.

**Lesson:** you don't fix "overwhelming" by showing less. You fix it by making the
important thing obvious and the rest one predictable click away.

### Front Office Football 8 and OOTP: depth is the draw, the interface is the complaint
- Operation Sports gave FOF8 8.5/10 and called it the premier football text sim; its
  listed con was the "outdated interface" and menus that "could be less cluttered".
  The reviewer said that without the interface it would be an all-time classic. A Steam
  user called the interface "at best confusing, and at worst a mess".
- A long-time FOF forum poster complained about too many separate floating windows,
  including a huge schedule window that did little. Their fix: make one central hub
  that shows only the current stage of the season and holds the full menu, and group
  tasks by how people actually play (for example one game-planning screen).
- Reviews of OOTP (the baseball equivalent) repeat the pattern: loved for depth,
  "extremely daunting" for new players, and one reviewer couldn't find a "home" screen
  that pulled things together. OOTP's own fixes over the years: freeing side space for
  stats, customizable player lists, filters and right-click menus. OOTP 27's stated
  goal is to modernize the screens players touch most often.

**Lesson:** players of these games want everything. What they ask for is a home base
and fewer, better-organized windows.

### Crusader Kings 3: complexity you can learn by hovering
Crusader Kings 3 is as dense as strategy games get, yet reviewers call it the most
approachable game Paradox has made, mostly because of **nested tooltips**: hover a
term, a small box explains it, and terms inside that box can be hovered too. Only one
stack is open at a time. Paradox liked it enough to build Europa Universalis V's
tooltips around it. CK3 also gathers low-urgency alerts in one spot so they don't
clutter the screen.

The warning from the same company: Victoria 3's launch reviews said key information
was "hidden beneath layers and layers of text", mostly in tooltips, with too many
clicks and windows; a long-time player said Victoria 2 kept the important information
on one screen.

**Lesson:** hover explanations are great for *explaining*. They must never be the
only place important numbers live.

### Data-heavy tools: density is fine when it's consistent and fast
- **Bloomberg Terminal** (what traders use, famous for dense screens): its designers
  describe their job as hiding complexity until it's needed, and they treat even small
  changes (a font, moving a button) as disruptive, because experts rely on things
  being where they always are.
- **"UI density" (Matt Strom's framework):** density isn't how crowded a screen looks.
  It's the value you get divided by the time and space the screen uses. Remove
  decoration, keep the spacing that shows what belongs together, and make things
  fast. A screen that responds in under a tenth of a second feels instant; 1-10
  seconds needs a spinner; longer needs a progress bar or let the user do something
  else.
- **Shneiderman's "mantra"** (a classic from 1996 research on data screens):
  *overview first, zoom and filter, then details on demand.* That's the three layers
  in the short version above.
- **Stephen Few on dashboards:** a dashboard is the most important information on
  *one screen*, readable at a glance, with no scrolling; if you have to remember
  something from another screen, it's failing. Numbers need context (a trend or a
  comparison) to mean anything. His list of mistakes includes too much precision,
  meaningless variety, clutter, weak highlighting of the key data, and misused color.
- **Nielsen Norman Group on data tables:** put the human-readable name first; order
  columns by importance and keep related ones together; freeze the header row and the
  name column when a table is bigger than the screen; use zebra striping or row
  highlighting; make filters obvious and show clearly when one is on; let people
  hide and reorder columns and sort. For looking at one row in detail, a side panel
  that leaves the table visible beats a pop-up that covers it.
- **Tabs:** design system guides (citing Nielsen Norman) put the limit around 5-7 tabs
  in one row; past that, use grouped menus or a sidebar.
- **Sparklines** (Edward Tufte): "word-sized" charts that sit inside a table cell.
  Sports pages have used them for win-loss streaks in standings for years.

### News as the glue
Football Manager's inbox is where the season's story reaches you: since FM 2017 you can
act on a message right from the inbox, it added a social media feed beside the news,
and FM27 times news to the season's rhythm (previews, mid-season, title races) and
color-codes urgency. Reviewers also noticed recycled comments over long careers.
That matches what Bitter and `news_words.py`'s Writer are already doing.

---

## 3. Recommendations (biggest payoff first)

### A. Add a home screen ("Front Office")
The tab you land on. Fits on one screen without scrolling. Every box links to the full
page it summarizes. Suggested contents:
- **This week:** opponent with both records, date, Watch my game / Sim week.
- **Needs your attention:** the to-do list that sits on top of Roster now (injury moves,
  game-day shortfalls), plus expiring contracts, offers waiting, draft on the clock,
  ranked by urgency and color-coded. Each item has its action button right there, the
  way FM lets you act from the inbox.
- **Last game:** score and a few lines, with the game summary pop-up one click away.
- **Your division:** a small standings table with a win-loss sparkline per team.
- **Around the league:** the top 3-5 Bitter stories.
- **Your team's leaders** and the most important injuries.

During the offseason the same screen shows the current phase, what it means, what you
still need to decide, and the Next button. This is the "central hub showing only the
current stage" the FOF forum poster asked for, and the "home" the OOTP reviewer couldn't
find. Once it exists, the Roster tab can drop its to-do box.

### B. Take back the vertical space
Merge the three top bands into one slim bar (about 60 px instead of about 230):
team logo/abbreviation and record, week and date, this week's game, Sim week, Save,
and a menu holding Save a copy and Main menu. The big team banner can live on the home
screen and the team page. Then put each tab's filters on **one** row, and let the main
table fill the rest of the window with the page scrolling as a whole (or at least a
much taller table). Target: 25+ roster rows visible at 1600x900 instead of about 9.
This is the cheapest change with the most visible effect.

### C. Group 12 tabs into about 6 hubs
One way to group them (the names are Blake's call):

| Hub | Inside |
|---|---|
| Home | the new home screen |
| Team | Roster, Depth chart (with Position counts folded in as a side panel), Contracts |
| Schedule | Schedule, Game (watch live), Playoffs bracket |
| League | Standings, Stats, Awards |
| Draft & Free agency | scouting, the draft room, free agent signings |
| Bitter | news and social |

Each hub opens to a sub-page you can choose (FM27's "landing spot" idea): for example
Team could open straight to Depth chart. Use one consistent sub-tab row in the same spot
on every hub so the screens feel like one product.

### D. Keep pop-ups for details, full pages for work
The Oct 21 pop-up decision holds up well against the research for player cards, game
summaries and the offseason report: quick look, close, you're back exactly where you
were. Draw the line there. Anything you work through for a while (the draft board,
free agency bidding, the depth chart, a long stat table) stays a full page, because
FM26's main complaint was work trapped in windows and FM27 is moving those back to
full pages. The Roster side panel (non-blocking detail next to the table) is the best of
both and is worth using on other tables, such as Stats player rows and the free agent
list, before reaching for a pop-up.

### E. One team context, always visible
One team picker, in the slim top bar. When you're looking at a team that isn't yours,
the bar changes color or shows "Viewing: Dallas (view only)" with a "Back to my team"
button. Remove the separate picker inside Stats, or have it follow the top one.

### F. Hover explanations everywhere (the Crusader Kings approach)
A shared glossary in the engine (plain-language text for terms like PUP, elevation,
practice squad eligibility, Endurance, fifth-year option, June 1 cut, the rating words)
and a small helper on the screen side that underlines a term and shows the explanation
on hover, with nested terms hoverable too. Rule: explanations go in tooltips; numbers
you need to make a decision never live *only* in a tooltip. This also matters if the
game is ever on Steam, where players won't know FOF8.

### G. Tables built for comparing
Following the Nielsen Norman guidance: name first, header and name column frozen,
hover highlight on the row, a visible "filtered" tag when a filter is on, and saved
views (pick columns once, they stay; FM fans specifically complained about views
resetting). A "Compact / Comfortable" row-height switch is cheap and lets you choose
how dense the tables feel.

### H. Small charts where they tell a story
Sparklines are content that adds depth without adding clutter:
- win-loss streaks in standings and on the home screen,
- a player's rating history on the player card (this is exactly where the development
  drama Blake loves, potential shifting up and down, would show at a glance),
- a game-by-game line in a player's season stats,
- cap space by year on Contracts.

### I. Color with a job
Rating colors and the "needs attention" yellow are meaningful; keep them. Make
position colors small chips rather than large blocks, and avoid adding new colors for
decoration. When fewer things are colored, the things that are colored get noticed.

### J. Speed and the keyboard
Experts move fast in dense tools when keys do the work: number keys or letters for
hubs, Space for Sim week, arrow keys through a table with the side panel following,
Esc to close a pop-up (already done). Keep slow work visible: Bitter's rebuild takes
seconds late in a season, so it should show a loading indicator or build in the
background after each sim.

### Things to avoid (from the research)
- Replacing tables with summary cards or tiles that hold less data (FM26).
- Burying important numbers in tooltips (Victoria 3).
- Many free-floating windows for ongoing work (FOF8, FM26).
- Moving things around between versions without a reason. Experts learn where things
  are, and that knowledge is part of what makes a dense game feel easy (Bloomberg).
- Hiding features behind tutorials or unlocking them gradually. Blake is an expert;
  calm defaults plus "More columns" style options do the same job without hiding
  anything.

## 4. Suggested order to build
1. **B (slim header, taller tables)**: small, screen-only, and you'll feel it at once.
2. **A (home screen)** and moving the Roster to-do list onto it.
3. **C (hubs)** together with **E (one team context)**, since both touch the top
   navigation.
4. **F, G, H** a piece at a time, starting with the player card's rating history
   sparkline once player development's rating history is saved.
5. **J** whenever, it's cheap.

All of this is in `screens/`; `engine/` would only gain the glossary text and, if it
isn't already stored, rating history per season.

## 5. Open questions for Blake
1. Do you want a home screen to be the tab you land on? What's on it that I haven't
   listed (or should come off)?
2. Hub names and grouping: does the table in C match how you think about the game?
   Where should Contracts live: with the team, or with Draft & Free agency?
3. Should Position counts become a side panel on Depth chart instead of its own tab?
4. How much customizing do you want: just choosing each hub's first page, or also
   rearranging boxes on the home screen?
5. Default row height: dense like FOF8, or a little roomier?

## Sources
- Football Manager 27 interface deep dive: [footballmanager.com, "FM27: Clearer Interface & Smoother Navigation"](https://www.footballmanager.com/nl/node/1099), [TheSixthAxis](https://www.thesixthaxis.com/2026/09/22/f..), [Dork](https://readdork.com/gaming/football-manager-27-interface-deep-dive-ea702a66ac), [Sortitoutsi: FM27 bringing back immersion](https://sortitoutsi.net/content/77790/fm27-bringing-back-immersion), [FM27: A Deeper, More Immersive Football World](https://www.footballmanager.com/node/1101)
- Football Manager 26 reception: [FRVR: 9 things FM26 needs to fix](https://frvr.com/blog/news/9-things-football-manager-26-needs-to-fix-immediately-to-get-back-on-side), [Digitec: FM26 floundering in an interface labyrinth](https://www.digitec.ch/en/page/football-manager-26-is-floundering-in-an-interface-labyrinth-40507), [PC Gamer FM26 review](https://www.pcgamer.com/games/sports/football-manager-26-review/), [GameSpot FM26 review](https://www.gamespot.com/reviews/football-manager-26-review-back-to-the-drawing-board/1900-6418437/), [FM26 UI feature page](https://www.footballmanager.com/fr/node/960)
- Earlier Football Manager inbox and news: [PC Gamer FM2017 review](https://www.pcgamer.com/football-manager-2017-review), [Football Manager 2014 (Wikipedia)](https://en.wikipedia.org/wiki/Football_Manager_2014)
- Front Office Football: [Operation Sports FOF8 review](https://osftw.com/reviews/853/front-office-football-eight), [Steam discussion](https://steamcommunity.com/app/547900/discussions/0/154641879451418578), [FOFC forum post on windows and a central hub](https://forums.operationsports.com/fofc/showthread.php?p=3019218)
- OOTP: [OOTP 19 review, Game Chronicles](https://gamechronicles.com/out-of-the-park-baseball-19-review-pc), [OOTP 12 review, Operation Sports](https://www.osftw.com/reviews/611/out-of-the-park-baseball-12), [OOTP 13 developer newsletter](https://www.ootpdevelopments.com/newsletters/nl0090/), [OOTP 15 review](https://gmgames.org/out-of-the-park-baseball-ootp-2015/review/), [OOTP 27 UX refresh, Sports Gamers Online](https://www.sportsgamersonline.com/?p=80069)
- Paradox: [nested tooltips discussion (WHATWG issue)](https://github.com/whatwg/html/issues/9776), [Tinto Talks dev diary thread](https://admin-forum.paradoxplaza.com/forum/developer-diary/tinto-talks-77-20th-of-august-2025.1856053/page-3), [CK3 console impressions, Wccftech](https://wccftech.com/crusader-kings-iii-console-ps5-xbox-series-x-impressions/amp/), [Victoria 3 review, eXputer](https://exputer.com/reviews/victoria-3/), [Victoria 3 UI overhaul, Gamepressure](https://www.gamepressure.com/S013-amp.asp?ID=20696)
- Density and data design: [Bloomberg: how Terminal UX designers conceal complexity](https://www.bloomberg.com/company/stories/how-bloomberg-terminal-ux-designers-conceal-complexity), [Matt Strom: UI density](https://mattstromawn.com/writing/ui-density), [UX Magazine: the impossible Bloomberg makeover](https://uxmag.com/articles/the-impossible-bloomberg-makeover), [Shneiderman 1996, "The Eyes Have It"](https://webspace.science.uu.nl/~telea001/uploads/VACourse/Shneiderman96.pdf), [Stephen Few's 13 dashboard mistakes (summary)](https://www.thedataschool.co.uk/anh-vu/are-you-making-these-13-dashboard-design-mistakes/), [Nielsen Norman Group: data tables, four major user tasks](https://www.nngroup.com/articles/data-tables/), [JetBrains tab bar guidance](https://jetbrains.com/help/ring-ui/tab-bar.html), [Galaxus tabs guidance](https://galaxus.ch/designsystem/components/tabs-design)
- Sparklines: [Tufte: sparkline theory and practice](https://www.edwardtufte.com/notebook/sparkline-theory-and-practice-edward-tufte/), [Juice Analytics: restoring romance to the sports page](https://www.juiceanalytics.com/writing/restoring-romance-to-the-sports-page), [Neoformix: MLS sparklines](https://neoformix.com/2011/MLSSparklines.html)

Caveats: several sources are reviews, forum posts or summaries of the original guidance
(I couldn't open the GameSpot review, the FOFC thread or the Bloomberg post directly,
so those points come from search summaries). FM27's changes are announced, not yet
tested by players.
