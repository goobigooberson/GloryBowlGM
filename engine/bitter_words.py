# bitter_words.py
# What the accounts on Bitter (the league's social media site, the News tab)
# sound like. Same format as engine/news_words.py: {fact} is filled in by the
# code, #name# drops in a pick from another list, (text, "needs") entries are
# only used when those facts are true.
#
# Tone (Blake, Oct 23): PG-13. Trash talk, roasts, hot takes, sarcasm and
# memes; no swearing or slurs. Every account is invented; none imitates a
# real person. Opinions are allowed (that's the point); made-up facts aren't.

BITTER_BANK = {
    # ---- Team accounts (official) ---------------------------------------------
    "team_win": [
        "FINAL. {me} {my}, {them} {their}. {tag}",
        "W. {tag}",
        "That's a dub. {me} {my}, {them} {their}. {tag}",
        "{me} win! {rec} on the season. {tag}",
        "Enjoy this one, {city}. {tag}",
        "Final from today: {me} {my}, {them} {their}. {tag}",
        ("{star_last} game. {tag}", "star"),
        ("Somebody get {star_last} some ice. He earned it. {tag}", "star"),
        ("{streak_n} straight. {tag}", "streak3"),
        ("We'll take that one. {my}-{their}. {tag}", "close"),
    ],
    "team_loss": [
        "Final: {me} {my}, {them} {their}.",
        "Tough one today. Final: {me} {my}, {them} {their}.",
        "Not the result we wanted. Back to work.",
        "Final score. We'll be back next week.",
        ("Final: {me} {my}, {them} {their}. {star_last} with a big day in the loss.", "star"),
    ],
    "team_playoff_win": [
        "SURVIVE AND ADVANCE. {me} {my}, {them} {their}. {tag}",
        "We're moving on. {tag}",
        "On to the next one. {tag}",
    ],
    "team_champ": [
        "CHAMPIONS. {tag}",
        "{city}, this one's for you. {champ} CHAMPIONS. {tag}",
        "We did it. {champ} champions. {tag}",
    ],
    "team_clinch_berth": ["CLINCHED. Playoff football is coming to {city}. {tag}", "We're in. {tag}",
                          "January plans: made. {tag}"],
    "team_clinch_div": ["{div} Division champions. {tag}", "The {div} runs through {city}. {tag}",
                        "Division champs. {tag}"],
    "team_clinch_top": ["The road to {champ} goes through {city}. {tag}", "No. 1 seed. Home field. {tag}"],
    "team_pick": [
        "With the No. {pick} pick in the {season} draft, the {T} select {pos} {name}, {college}. {tag}",
        "Welcome to {city}, {name}! {tag}",
        "Our newest {Nick}: {pos} {name} out of {college}. {tag}",
    ],
    "team_sign": ["Welcome to {city}, {name}! {tag}", "We've signed {pos} {name}. {tag}",
                  "Roster move: we've signed {pos} {name}."],
    "team_back": ["Look who's back. {tag}", "{last} is back. {tag}", "Welcome back, {last}."],
    "team_retire": ["Thank you, {name}. Forever a {Nick}.", "Congratulations on a great career, {name}. {tag}"],

    # ---- Rex Harmon: TV host, hot takes ----------------------------------------
    "rex_done": [
        "{Tc} is DONE. Stick a fork in them. {rec} and going nowhere.",
        "I'm calling it right now: {Tc} misses the playoffs. Write it down.",
        "{Tc} at {rec}? Blow it up. Start over. I'm serious.",
        "Nobody wants to hear it but {Tc} is finished. FINISHED.",
        "{Tc} is the most disappointing team in this league and it's not close.",
    ],
    "rex_champ": [
        "{Tc} is winning it all. I said what I said.",
        "{Tc} is the best team in football and it's not close.",
        "Book it: {Tc} in {champ}. Bookmark this.",
        "Every other team is playing for second. {Tc} is THAT team.",
    ],
    "rex_fraud": [
        "{Lc} just lost to {Wc}. FRAUDS. I've been saying it all year.",
        "{Lc} came in {lrec_b} and lost to THAT team? Fraud alert.",
        "Told you {Lc} was a paper tiger. {score}. Paper. Tiger.",
    ],
    "rex_player": [
        "{name} is the best {pos_word} in this league. Don't @ me.",
        "Put {name} in the Hall of Fame right now. I'll wait.",
        "If {name} isn't in the MVP talk, I don't want to hear from you.",
    ],
    "rex_rank": [
        "{top} at No. 1? Please. Ask me in January.",
        "These power rankings are a joke. {top} hasn't beaten anybody.",
        "{top} on top of the rankings and I'm supposed to be scared? Not buying it.",
    ],
    "rex_right": [
        "Week {k}: I said {Tc} was done. {Tc} finished {rec}. You're welcome.",
        "Remember when everybody laughed at me for saying {Tc} was finished? {rec}. Who's laughing now.",
    ],
    "rex_right_champ": [
        "Week {k}: I said {Tc} was the team to beat. {Tc} just won {champ}. Some of us know ball.",
    ],
    # ---- Receipts account ---------------------------------------------------------
    "receipts": [
        "Receipts. {Tc} is {since_rec} since this take.",
        "This aged like milk. {Tc}: {since_rec} since.",
        "Just leaving this here. {Tc} has gone {since_rec} since.",
        "Bookmarked it so you didn't have to. {Tc}: {since_rec}.",
        "Rex, buddy. {Tc} is {since_rec} since you said this.",
    ],
    # ---- Walt Brennan: grumpy columnist ---------------------------------------------
    "walt_unbeaten": [
        "Everybody's crowning {Tc} at {rec}. Ask me again in January.",
        "{Tc} is {rec}. Nice. Nobody hands out rings in the regular season.",
    ],
    "walt_passing": [
        "{name} threw for {yds_n} yards and everybody's losing their minds. Win a game in the snow, then we'll talk.",
        "{yds_n} passing yards. Fine. Back in my day we ran the ball and liked it.",
    ],
    "walt_rush": [
        "{Wc} ran for {rw} yards. Football the way it's supposed to be played. More of that, please.",
        "Somebody finally remembered you can hand the ball off. {Wc}, {rw} rushing yards. Beautiful.",
    ],
    "walt_lowscore": [
        "{Wc} {ws}, {Lc} {ls}. The kids will call it boring. I call it football.",
        "A {score} game. Defense, field position, a punter earning his money. I loved every minute.",
    ],
    "walt_shootout": [
        "{Wc} {ws}, {Lc} {ls}. Does anybody play defense anymore? Honest question.",
        "{score}. That's not a football game, that's a track meet.",
    ],
    "walt_generic": [
        "Hot take from an old man: the team that tackles better usually wins. Watch {Wc} sometime.",
        "Another week, another round of people overreacting. {Wc} is {wrec}. Calm down, everybody.",
    ],
    # ---- Fantasy Freddie ---------------------------------------------------------------
    "freddie_boom": [
        "If you started {last} this week, congratulations, you're printing points.",
        "{last} with {got}. League-winner behavior.",
        "Benched {last} this week? Delete the app. Go outside.",
        "{last} just won somebody their matchup with {got}.",
        "Me watching {last} on my bench: this is fine.",
    ],
    "freddie_injury": [
        "{name} ({part}) {vp}. Check your waiver wire, people.",
        "Ugh. {name} {vp}. Fantasy managers, pour one out.",
        "{name} {vp}. That one hurts my fantasy team too.",
    ],
    "freddie_bust": [
        "{last} threw {ints} interceptions. My fantasy team is in shambles.",
        "Started {last} this week. {ints} picks. Do not talk to me.",
    ],
    # ---- Big T Holloway: ex-lineman, film guy -------------------------------------------
    "bigt_sacks": [
        "{Lc} gave up {n} sacks. That's not on the quarterback. Film don't lie.",
        "{n} sacks allowed by {Lc}. That front five needs a long week of practice.",
        "Watched {Wc} bully {Lc} up front: {n} sacks. Grown man football.",
    ],
    "bigt_rush": [
        "{Wc} ran for {rw} yards. That's the big boys up front eating. Love to see it.",
        "{rw} rushing yards for {Wc}. Somebody buy that offensive line dinner.",
    ],
    "bigt_def": [
        "{name} lived in the backfield today: {got}. Film don't lie.",
        "{name} was a problem with {got}. Offensive coordinators will be up late this week.",
    ],
    # ---- Gridiron Memes (parody) -----------------------------------------------------------
    "meme_shutout": [
        "{Lc} offense today: error 404, points not found.",
        "{Lc} scored as many points as I did today. Zero.",
        "{Lc} really said \"defense wins championships\" and forgot the other half.",
    ],
    "meme_blowout": [
        "{Lc} fans at halftime: *quietly leaves*",
        "{Wc} {ws}, {Lc} {ls}. Someone call the authorities.",
        "{Lc} got sent to the shadow realm. {score}.",
        "Me checking the {Wc}-{Lc} score: oh. oh no.",
    ],
    "meme_ot": [
        "Overtime in {Wc}-{Lc}. My heart rate: yes.",
        "{Wc}-{Lc} went to overtime and I aged five years.",
    ],
    "meme_comeback": [
        "{Lc} was up {max_def} and still lost. Never leave early.",
        "{Lc} blew a {max_def}-point lead. A tale as old as time.",
        "Friendly reminder that {Lc} led by {max_def} today.",
    ],
    "meme_winless": [
        "{Lc} is {lrec}. At least the draft pick is looking good.",
        "{Lc} fans this season: it's not a rebuild, it's a lifestyle.",
        "{Lc} at {lrec}. Somebody check on them.",
    ],
    "meme_kicker": [
        "Kickers are football players too. {kicker} with the game-winner. Respect.",
        "{kicker} hitting the game-winner like it's nothing. Kickers deserve love.",
    ],
    "meme_irrelevant": [
        "Shoutout to {name}, pick No. {pick}. Mr. Irrelevant is very relevant to us.",
        "Last pick in the draft: {name}. Underdog story starts now.",
    ],
    "meme_champ": [
        "{Wc} fans tonight: absolutely nobody is sleeping.",
        "{Wc} winning {champ} and everybody who doubted them suddenly quiet.",
    ],
    "meme_streak_loss": [
        "{Lc} has lost {n_l} straight. At this point it's a choice.",
        "{n_l} straight losses for {Lc}. The fans deserve hazard pay.",
    ],
    "meme_streak_win": [
        "{Wc} has won {n_w} straight and somebody needs to stop them before it gets weird.",
        "Nobody:\n{Wc}: {n_w} straight wins.",
    ],
    # ---- Celebrities (fictional) --------------------------------------------------------
    "celeb_win": [
        "{NICK} WIN!!! {city} stand up!",
        "Big W for my {Nick}!! {tag}",
        "{Nick} forever. Nothing else to say. {tag}",
        ("{star_last} is HIM. {tag}", "star"),
    ],
    "celeb_win_rapper": ["{NICK} on my chain fr. {tag}", "{city} we up!! {tag}",
                         ("{star_last} cooked. Putting him in my next video.", "star")],
    "celeb_win_popstar": ["Crying in the club over this {Nick} win", "{Nick} fans we eat tonight!! {tag}"],
    "celeb_win_country": ["Ain't nothin' like a {Nick} win. {tag}",
                          "Writing a song about this {Nick} game. Working title: {score}."],
    "celeb_win_actress": ["Took a break from set to watch the {Nick}. Worth every minute. {tag}",
                          "Best performance I saw all week? The {Nick}. {tag}"],
    "celeb_win_comedian": ["My therapist says I'm too invested in the {Nick}. My therapist is wrong. {tag}",
                           "Doing a set tonight and every joke is going to be about this {Nick} win."],
    "celeb_win_hoops": ["Big W for the {Nick}! {city} stand up! {tag}",
                        "Got to see that {Nick} game between my own games. Let's go!"],
    "celeb_win_chef": ["Cooking up something special tonight to celebrate. {Nick} W.",
                       "That {Nick} win was a five-course meal. {tag}"],
    "celeb_win_wrestler": ["THE {NICK} JUST BODY SLAMMED THE {OPP}!!! {tag}", "OHHH YEAHHH {NICK} WIN!!!"],
    "celeb_win_dj": ["Turning it all the way up for the {Nick}!! {tag}",
                     "Playing the {Nick} fight song at the club tonight. Deal with it."],
    "celeb_win_host": ["Tomorrow's show is going to be ALL {Nick}. Sorry, not sorry.",
                       "Producers, clear the rundown. We're talking {Nick} tomorrow."],
    "celeb_win_close": ["{Nick}, please. For my health.", "My heart cannot take another one like that. {Nick} W.",
                        "I aged ten years watching that. Worth it. {tag}", "WHO SCHEDULED THAT ENDING. {Nick} WIN.",
                        "Somebody check my blood pressure. {NICK} WIN!!"],
    "celeb_loss": ["Not talking about it.", "I need a minute.", "Logging off for the night.",
                   "We'll get them next week. I think.", "Turning my phone off. Goodnight."],
    # ---- Player personalities (most players are generic; a few are not) ------------------
    "player_win_bold": ["Told y'all. Nobody in this league can guard me.", "They gonna learn.",
                        "{opp} wasn't ready. Nobody is.", "Put some respect on {city}.", "Easy work.",
                        "Write my name down in pen.", "That's what happens when you test me."],
    "player_loss_bold": ["We'll see them again. Bet on it.", "That ain't happening twice.",
                         "Everybody got jokes now. Watch next week.", "Enjoy it. It won't last."],
    "player_cryptic": ["👀", "...", "Patience.", "Noted.", "Everything happens for a reason.", "Quiet.",
                       "Loyalty is rare these days.", "Some of y'all are gonna be real quiet soon.",
                       "It is what it is.", "🤐", "Growth.", "Remember this.", "Moving in silence.",
                       "Funny how things work out.", "Not everybody is meant to understand."],
    "player_weird": ["Pineapple on pizza is elite. I will not be taking questions.",
                     "Thinking about getting a pet alligator. Name suggestions?",
                     "Does anybody actually like airport food or are we all pretending",
                     "Spent the off day building a birdhouse. Proud of it.", "Who's up for chess? Real question.",
                     "Hot dogs are sandwiches. Fight me.",
                     "If I wasn't playing football I'd be a professional napper.",
                     "Just watched a documentary about octopuses. They're smarter than us. Think about it.",
                     "Learning the accordion. Teammates are not thrilled.",
                     "Cereal is a soup. I will die on this hill."],
    "player_guarantee": ["We winning Sunday. Guarantee it.", "{opp} is gonna have a long day. Mark it down.",
                         "I don't make predictions. I make promises. W this week.",
                         "Bookmark this: we beat {opp} this week."],
    "player_told": ["Told y'all.", "Promise kept.", "I said what I said.", "Guaranteed it. Delivered it."],
    "receipts_player": ["{name} guaranteed a win. {Tc} lost {score}.", "Promise broken. {Tc} lost {score}.",
                        "Remember this one? {Tc} lost {score}."],
    "celeb_champ": ["CHAMPIONS!!! {CITY} WE DID IT!!!", "I'm not crying, you're crying. {champ} CHAMPS. {tag}",
                    "{Nick} fans: we waited, we believed. CHAMPIONS. {tag}"],
    "celeb_clinch": ["PLAYOFFS!!! {tag}", "{city} is going to the playoffs and I'm going to every game. {tag}"],
    "celeb_draft": ["Welcome to {city}, {last}! Can't wait to see you play.", "Love the {last} pick. {tag}"],
    # ---- Fans: moods -----------------------------------------------------------------
    "fan_rival_dunk": [
        "{opp} lost again lol",
        "Imagine being a {opp} fan right now. Couldn't be me.",
        "{opp} fans awfully quiet today.",
        "Thoughts and prayers to {opp} fans. Just kidding.",
        "{opp} losing is my favorite part of the week.",
    ],
    "fan_salty": [
        "Refs.", "Enjoy it while it lasts.", "Lucky.", "We'll see you again.", "Ok and? We're still better.",
        "That was a fluke and everybody knows it.",
    ],
    "fan_reply_win": [
        "LET'S GOOOO", "Never doubted it", "Love this team", "W W W", "Best fanbase in the league",
        "Book the parade (kidding) (unless?)", ("{star_last} deserves a raise", "star"),
    ],
    "fan_reply_injury": ["No no no no", "Not him. Anyone but him.", "Season just got a lot harder",
                         "Heal up, we need you", "Next man up I guess"],
    "fan_reply_pick": ["Love it", "Who??", "Never heard of him, trusting the process", "Great value there",
                       "Not who I wanted but ok", "Welcome to the family"],
    "fan_reply_rank": ["Disrespect", "Too low", "Fair", "We'll prove you wrong", "Way too high honestly"],
    # ---- Outlets ----------------------------------------------------------------------------
    "wire_game": ["{headline}", "{headline}", "RECAP: {headline}"],
    "wire_news": ["{headline}", "NEWS: {headline}"],
    "daily_feature": ["{headline}", "NEW: {headline}", "Read: {headline}"],
    "insider_breaking": ["BREAKING: {headline}", "{headline}", "Sources: {headline}"],
}
