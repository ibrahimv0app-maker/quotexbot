# BLACK TORNADO — GitHub → Railway (Roman Urdu)

## 0. Token ko secure karein

Aapka token chat mein share hua tha. Telegram **@BotFather** mein `/revoke` use karke is bot ka naya token banayein. Naya token **sirf Railway Variables** mein paste karein—GitHub, source code, ZIP, screenshot ya chat mein nahi.

Channel `-1003501100081` project mein default target hai; Railway mein bhi isi ID ko explicitly set karein. Bot channel ka admin rehna chahiye aur **Post Messages** permission on honi chahiye.

## 1. GitHub repository banayein

Is delivery se GitHub par push **nahi** hua: is session mein GitHub integration/authenticated login available nahi tha. Aapke GitHub account par koi repo create hone ka claim nahi hai.

1. `black-tornado-github-ready.zip` download karke extract karein.
2. GitHub par ek **private**, empty repository banayein, misal `black-tornado`.
3. GitHub Desktop ka authenticated login use karein, ya apne computer par Git terminal. Token chat mein dene ki zaroorat nahi.
4. ZIP ke andar wale `black-tornado` folder mein terminal kholein:

```bash
git init
git add .
git commit -m "BLACK TORNADO boxed Telegram format and tested delivery"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/black-tornado.git
git push -u origin main
```

`YOUR_USERNAME`/repository URL apne repo se replace karein. GitHub ka normal browser/credential-manager login use karein. `.env` Git se excluded hai. Source root mein `Dockerfile`, `railway.toml`, `requirements.txt`, `app/`, aur dono JSON settings hon—extra parent folder ko repository root mat banayein.

GitHub web upload use karna ho to extracted **files/folders** upload karein, ZIP ko akela upload na karein. Hidden `.github/` CI files terminal/GitHub Desktop se sahi include hoti hain. Evidence/tick archives deployment ZIP mein jaan-boojh kar nahi rakhe gaye; full evidence alag full package mein hai.

## 2. Railway persistent service

1. Railway par naya project banayein aur **PostgreSQL** service add karein.
2. Isi project mein application service ko apne GitHub repo se deploy karein.
3. Bot service ke **Variables** mein PostgreSQL service ka `DATABASE_URL` reference add karein. Database reference ke liye Railway ka variable-reference picker use karein; service name badal sakta hai.
4. Ye application variables set karein:

| Variable | Value |
|---|---|
| `DATABASE_URL` | PostgreSQL service ke DATABASE_URL ka reference |
| `TELEGRAM_BOT_TOKEN` | Naya regenerated BotFather token — secret |
| `TELEGRAM_CHAT_ID` | `-1003501100081` |
| `DRY_RUN` | Pehle `true`; checks ke baad `false` to enable real channel messages |
| `KILL_SWITCH` | `false` |
| `TELEGRAM_INCLUDE_AUDIT_DETAILS` | `false` |
| `DISPLAY_TIMEZONE` | `Asia/Karachi` |
| `ADMIN_API_KEY` | Apni strong random secret value |

Agar database service ka naam `Postgres` hai to reference aksar `${{Postgres.DATABASE_URL}}` hota hai; **apne service ka actual reference select karein**, andaza nahi. Public DB URL ki bajaye project ka internal reference use karein.

Dockerfile aur `railway.toml` already diye gaye hain. Start command `python -m app.main`, healthcheck `/health`, **one replica**, long-running service—not cron. App Railway ka `PORT` use karta hai; manually localhost URL set na karein.

## 3. Verify, phir Telegram delivery on karein

1. Deploy logs mein database connected aur service started check karein.
2. Generated service domain par `/health`, `/health/feeds`, `/stats` dekhein. Feed-ready count zero ho to Telegram on karne se pehle problem resolve karein.
3. Optional: service terminal/local equivalent configured environment mein `python -m app.cli telegram-test --send` chalayein. **Do TEST messages channel mein jayenge**; ye trade nahi hain. Har startup par automatic test nahi hota.
4. Jab ready hon, Railway mein `DRY_RUN=false` save karke redeploy karein. Is mode ko token, channel aur PostgreSQL ki zaroorat hai; missing configuration par app fail karega, silently pretend nahi karega.
5. Ab **valid setup milne aur entry-window match hone par** isi configured channel mein signal aur baad mein result jayega. Valid setup nahi to NO SIGNAL—frequency force nahi hoti. Result ke liye boundary prices missing hon to UNVERIFIED, fabricated WIN/LOSS nahi.

Computer band hone par bhi Railway service chal sakti hai, jab tak aapki Railway hosting/resources active hon. Temporary Arena preview production hosting nahi hai. Railway deployment/Docker image build is environment mein perform nahi hua; Telegram posting test hua hai, actual profitability test nahi.

## 4. Completed Telegram check

Authorized real external check: bot admin/Post Messages verified; TEST signal message **27926**, TEST result **27927** accepted. The test result was **UNVERIFIED / delivery test only**, not a real win/loss. 348 automated tests pass, including the synthetic full publication/settlement path on SQLite and PostgreSQL.

Bot Quotex mein login ya order place nahi karta; sirf manual-entry signals/messages deta hai. BT score win probability nahi hai. Secret token rotate karke hi deploy karein.
