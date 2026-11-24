# Inbox Spy, by Walden

See every email your competitors send: flows vs campaigns, send times, subject lines, preview text and a screenshot of every email. Everything is sorted by month in a local app and on a Figma board, and syncs itself every week.

Setup takes about 30 minutes. After that you only open the app or the Figma board.

---

## What you need

- **A Mac** with **Google Chrome** installed. Chromium, Brave or Edge work too. Chrome takes the email screenshots in the background.
- **Python 3.** Check by opening Terminal and running `python3 --version`. If it isn't there, install it from python.org.
- **Claude Code**, ideally the **Claude desktop app**, which the weekly auto-sync needs. This needs a paid Claude plan (Pro or Max).
- **A Composio account.** It's free to start at composio.dev and connects Claude to Gmail.
- **A Figma account** for the boards.
- **A brand-new Gmail address** to use as your burner inbox. Never use your real inbox.

---

## Setup

### 1. Create your burner inbox (5 min)
Make a new Gmail account and use it only for this.

### 2. Sign it up to your competitors (10 min, then wait)
Go to each brand's website and enter the burner address in their sign-up pop-up or footer form. Confirm any "please confirm your subscription" emails.

Inbox Spy can only see emails sent after you sign up, so your boards fill up over the following days and weeks. Sign up today.

### 3. Connect Gmail and Figma to Claude (10 min)
1. In **Composio**, connect the **burner** Gmail account.
2. In **claude.ai → Settings → Connectors**, add **Composio** and **Figma**.
3. Restart the Claude app.

### 4. Install the skill (2 min)
Download **[inbox-spy.zip](https://github.com/ajwatters/inbox-spy/releases/latest/download/inbox-spy.zip)**, unzip it, and move the `inbox-spy` folder into:

```
~/.claude/skills/
```

The `.claude` folder is hidden in your home folder. In Finder, press **Cmd+Shift+G** and paste `~/.claude/skills/`. If the `skills` folder doesn't exist, create it.

### 5. Run setup (5–10 min)
Open Claude Code and type:

```
/inbox-spy setup
```

Claude checks your computer, then asks for:
- your burner address
- your Figma team
- your timezone
- the brands you want to track, as brand name plus the domain their emails come from, e.g. *Klik Camera, klikcamera.com*
- when the weekly sync should run (default: Sunday 9:00)

It then installs the **Inbox Spy** app in your Applications folder and Dock, runs the first sync and opens it.

---

## Using it

Click **Inbox Spy** in your Dock or Applications folder. It opens in its own window. It runs on your Mac, so your competitor emails never leave your computer.

For each brand:
- **Sync now** pulls new emails straight away, usually in 1–5 minutes.
- **Create Figma board** builds a Figma board of every email, one section per month, with send date and time, flow or campaign, subject line, preview text, sender name and a screenshot.
- **Open in Figma** opens the board. New emails are added to it on every sync.
- **Board / Table** views, **All / Campaigns / Flows** filters, date ranges like *BFCM this year*, and search.

You can also ask Claude in plain words:
- "Add Klik Camera, klikcamera.com"
- "What has Klik Camera been sending?"
- "Show me Klik's Black Friday emails"
- "Move the weekly sync to Monday 8am"

---

## Good to know

- **The weekly sync runs on your computer.** It only happens if your Mac is awake and the Claude app is open at that time. If it isn't, run **Sync now** whenever you like.
- **Syncs use your Claude usage.** A sync with nothing new is small. A first Figma board for a brand with lots of emails takes longer.
- **It's read-only.** Inbox Spy never sends, replies to, deletes or labels anything. It opens the first link in each email once, to read its tracking tags, which is how it tells flows from campaigns.
- **0 emails for a brand?** The burner probably isn't on their list yet. Sign it up again and confirm the opt-in email.
- Logs for each sync are in `~/.claude/skills/inbox-spy/logs/`.

---

## Want a better email strategy?

**👉 [Book a free 36-point email audit](https://links.waldenretention.com/widget/bookings/live-email-audit) 👈**

Walden runs your Klaviyo account through our North Star Audit and shows you exactly where the money is hiding in your flows and campaigns.
