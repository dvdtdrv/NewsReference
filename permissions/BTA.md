# Permission: BTA (Bulgarian News Agency)

**Date received:** 31 October 2026
**Asked about:** reading the public feed https://www.bta.bg/bg/rss/free with our program
(it was refused with HTTP 429), at most once every 30 minutes.
**Sent to:** newsnet@bta.bg (cc marketing@bta.bg)

## BTA's reply (as received by David)

> Здравейте, благодарим за запитването и споделената информация. Бихме могли да ви уверим, че не
> представлява проблем за нас достъпването на емисията чрез браузър и не представлява проблем за нас
> да я отваряте чрез вашата програма без значение от това по какъв точно начин я достъпвате особено
> при условие, че извършвате само по 1 четене на 30 минути. Бъдете свободни да правите каквото
> намерите за удобно, понеже уважаваме находчивостта на българските студенти.

## What we do based on it

- `feeds.py` marks BTA `as_browser`: for BTA only, the program introduces itself as a browser.
- It reads the feed once per run, and runs happen every 30 minutes. `gentle` stays on, so if BTA
  ever answers "too many requests" again, the program waits as long as BTA asks.

## Not covered by this reply (ask before relying on it)

- **Commercial use.** The reply refers to "students"; ask again before the project earns money.
- **Showing BTA's photos** on the site.
- **Attribution** requirements, if any.

Keep the original email (sender, date, full text) in the mailbox as the actual proof.
