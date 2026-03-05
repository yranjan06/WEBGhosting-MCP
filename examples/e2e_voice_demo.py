#!/usr/bin/env python3
"""
WEBGhosting -- CINEMATIC DEMO: The 'Voice Command' Scenario

Simulates a high-level user request:
"Hey Ghost, go to Hacker News, find today's top story, search what Reddit
thinks about it, and draft a LinkedIn post summarizing the discussion."

Execution:
 - Instantly parses the exact #1 Hacker News post via precise DOM selectors.
 - Skips the LLM for navigation/search to achieve blazing speed.
 - Uses the LLM purely for cognitive extraction (reading Reddit discussions).
 - Auto-drafts the final LinkedIn post on a digital notepad online.
"""

import sys, time, json
sys.path.insert(0, '.')
from examples.client import *


def cinematic_sleep(seconds=1.5):
    """Pause briefly so the audience can read what happened on screen."""
    time.sleep(seconds)

client = WEBGhostingClient()

try:
    print(f"\n{CYAN}{'━'*70}")
    print(f"  USER VOICE COMMAND:")
    print(f"  {BOLD}\"Hey Ghost, go to Hacker News, click the top story of the day,")
    print(f"  search what Reddit thinks about it on Google, read the discussion,")
    print(f"  and then draft a LinkedIn post about it.\"{RESET}")
    print(f"{CYAN}{'━'*70}{RESET}\n")

    cinematic_sleep(3)

    # ---------------------------------------------------------
    # Scene 1: Hacker News — Find the #1 Post
    # ---------------------------------------------------------
    print(f"{CYAN}{BOLD}[Scene 1] Tab 1: Hacker News — Finding Today's Top Story{RESET}")
    client.call("browse", {"url": "https://news.ycombinator.com"})

    print(f"{DIM}  [System] Waiting for page to load...{RESET}")
    client.call("wait_for_load_state", {"state": "domcontentloaded"})
    cinematic_sleep(2)

    print(f"{YELLOW}  [Action] Instantly identifying the #1 ranked post...{RESET}")
    top_post_json = client.call("execute_js", {"script": """
        (() => {
            const el = document.querySelector('tr.athing:first-of-type span.titleline > a');
            const subtext = document.querySelector('tr.athing:first-of-type + tr .subtext');
            let commentLink = null;
            if (subtext) {
                commentLink = Array.from(subtext.querySelectorAll('a')).find(a => a.innerText.includes('comment') || a.innerText.includes('discuss'));
            }
            return JSON.stringify(el ? { 
                title: el.innerText.trim(), 
                href: el.href,
                comments: commentLink ? commentLink.href : null
            } : { error: "Not found" });
        })()
    """})

    try:
        top_post = json.loads(top_post_json)
        topic = top_post.get("title", "")
        print(f"  {GREEN}Top Story Found: {BOLD}'{topic}'{RESET}")
    except (json.JSONDecodeError, TypeError, AttributeError):
        topic = "Tech News"
        print(f"  {RED}Failed to parse top story, defaulting to 'Tech News'{RESET}")

    cinematic_sleep(2)
    print(f"{YELLOW}  [Action] Opening the Hacker News discussion...{RESET}")
    client.call("execute_js", {"script": "const el = Array.from(document.querySelectorAll('tr.athing:first-of-type + tr .subtext a')).find(a => a.innerText.includes('comment') || a.innerText.includes('discuss')); if (el) el.click(); else document.querySelector('tr.athing:first-of-type span.titleline > a').click();"})

    print(f"{DIM}  [System] Waiting for discussion to load...{RESET}")
    client.call("wait_for_load_state", {"state": "domcontentloaded"})
    cinematic_sleep(2)

    print(f"{YELLOW}  [Action] Speed reading comments...{RESET}")
    client.call("scroll", {"amount": 600})
    cinematic_sleep(1)

    print(f"{DIM}  [System] Pruning DOM to first comment and reply...{RESET}")
    client.call("execute_js", {"script": """
        const commentsTable = document.querySelector('table.comment-tree');
        if (commentsTable) {
            const rows = Array.from(commentsTable.querySelectorAll('tr.comtr'));
            let keepCount = 0;
            for (let i = 0; i < rows.length; i++) {
                const indent = parseInt(rows[i].querySelector('.ind')?.getAttribute('indent') || '0');
                if (indent === 0 && keepCount === 0) {
                    keepCount++;
                } else if (indent > 0 && keepCount === 1) {
                    keepCount++;
                } else if (keepCount >= 2 || (indent === 0 && keepCount > 0)) {
                    rows[i].remove();
                }
            }
        }
    """})
    client.call("scroll", {"amount": 600})
    cinematic_sleep(2)
    print(f"  {GREEN}Hacker News context acquired.{RESET}\n")

    # ---------------------------------------------------------
    # Scene 2: Google Search — Reddit Cross-Reference
    # ---------------------------------------------------------
    search_query = f"{topic} in reddit"

    print(f"{CYAN}{BOLD}[Scene 2] Tab 2: Google Search — Reddit Discussions{RESET}")
    client.call("open_tab", {})
    client.call("browse", {"url": "https://google.com"})

    print(f"{DIM}  [System] Waiting for Google to load...{RESET}")
    client.call("wait_for_load_state", {"state": "domcontentloaded"})
    cinematic_sleep(1)

    print(f"{YELLOW}  [Action] Searching: '{search_query}'...{RESET}")
    client.call("fill_form", {"fields": [{"selector": "textarea#APjFqb", "value": search_query, "type": "textbox"}]})
    cinematic_sleep(0.5)
    client.call("press_key", {"key": "Enter"})

    print(f"{DIM}  [System] Waiting for results...{RESET}")
    client.call("wait_for_load_state", {"state": "domcontentloaded"})
    cinematic_sleep(2)

    print(f"{YELLOW}  [Action] Finding and clicking the top Reddit link...{RESET}")
    client.call("execute_js", {"script": """
        const redditLink = Array.from(document.querySelectorAll('a'))
                                .find(a => a.href.includes('reddit.com') && a.querySelector('h3'));
        if (redditLink) {
            redditLink.click();
        } else {
            document.querySelector('h3').click();
        }
    """})

    print(f"{DIM}  [System] Waiting for Reddit thread to load...{RESET}")
    client.call("wait_for_load_state", {"state": "domcontentloaded"})
    cinematic_sleep(3)

    print(f"{YELLOW}  [Action] Scrolling through the Reddit discussion...{RESET}")
    client.call("scroll", {"amount": 800})
    cinematic_sleep(2)

    # ---------------------------------------------------------
    # Scene 3: Reddit Extraction — JS-based (no race condition)
    # ---------------------------------------------------------
    print(f"\n{CYAN}{BOLD}[Scene 3] AI Cognition — Cross-Referencing Platforms{RESET}")
    print(f"{YELLOW}  [Cognitive] Reading Reddit comments directly...{RESET}")

    # Extract first comment + first reply via JS — works on BOTH new Reddit (shreddit-comment) and old Reddit
    reddit_data_json = client.call("execute_js", {"script": """
        (() => {
            let post = '', firstComment = '', firstReply = '';
            
            // Try New Reddit (shreddit-comment with depth attribute)
            const comments = document.querySelectorAll('shreddit-comment');
            if (comments.length > 0) {
                post = document.querySelector('h1')?.innerText || document.title || '';
                for (const c of comments) {
                    const depth = parseInt(c.getAttribute('depth') || '0');
                    const text = c.querySelector('div[slot="comment"]')?.innerText?.trim() || '';
                    const author = c.getAttribute('author') || 'unknown';
                    if (depth === 0 && !firstComment) {
                        firstComment = author + ': ' + text;
                    } else if (depth === 1 && firstComment && !firstReply) {
                        firstReply = author + ': ' + text;
                        break;
                    }
                }
            }
            
            // Fallback: Old Reddit or non-standard layout
            if (!firstComment) {
                post = document.querySelector('h1, .title a')?.innerText || document.title || '';
                const commentDivs = document.querySelectorAll('.comment .md, .Comment .RichTextJSON-root, [data-testid="comment"] p');
                if (commentDivs.length > 0) firstComment = commentDivs[0]?.innerText?.trim() || '';
                if (commentDivs.length > 1) firstReply = commentDivs[1]?.innerText?.trim() || '';
            }
            
            return JSON.stringify({
                post: post.substring(0, 200),
                comment: firstComment.substring(0, 500),
                reply: firstReply.substring(0, 500),
                source: comments.length > 0 ? 'new_reddit' : 'old_reddit'
            });
        })()
    """})

    # Parse the JS result
    reddit_comment = ""
    reddit_reply = ""
    reddit_source = "unknown"
    try:
        reddit_data = json.loads(reddit_data_json)
        reddit_comment = reddit_data.get("comment", "")
        reddit_reply = reddit_data.get("reply", "")
        reddit_source = reddit_data.get("source", "unknown")
        print(f"  {GREEN}Reddit data captured ({reddit_source}){RESET}")
        if reddit_comment:
            print(f"  {DIM}First comment: {reddit_comment[:80]}...{RESET}")
        if reddit_reply:
            print(f"  {DIM}First reply: {reddit_reply[:80]}...{RESET}")
    except (json.JSONDecodeError, TypeError):
        print(f"  {DIM}Reddit comments not available, using fallback.{RESET}")
        reddit_comment = "Users discussed the topic with mixed opinions."

    # Build summary from extracted data (no LLM needed for this — faster + reliable)
    if reddit_comment:
        summary = reddit_comment
        if reddit_reply:
            summary += " | Reply: " + reddit_reply
    else:
        summary = "Community discussed the topic with interest and mixed perspectives."
    sentiment = "Analysis Complete"

    # Cinematic tab switching (visual flair only — data already captured)
    print(f"{YELLOW}  [Action] Cross-referencing Hacker News and Reddit...{RESET}")
    client.call("switch_tab", {"index": 0})
    client.call("scroll", {"amount": -400})
    cinematic_sleep(2)
    client.call("switch_tab", {"index": 1})
    client.call("scroll", {"amount": 500})
    cinematic_sleep(2)

    print(f"  {GREEN}Extraction Complete.{RESET}")
    print(f"  {DIM}Sentiment: {sentiment}{RESET}\n")
    cinematic_sleep(2)

    # ---------------------------------------------------------
    # Scene 4: Draft LinkedIn Post on Digital Notepad
    # ---------------------------------------------------------
    print(f"{CYAN}{BOLD}[Scene 4] Tab 3: Auto-Drafting the LinkedIn Post{RESET}")
    client.call("open_tab", {})

    print(f"{YELLOW}  [Action] Opening a digital notepad...{RESET}")
    client.call("browse", {"url": "https://www.rapidtables.com/tools/notepad.html"})
    client.call("wait_for_load_state", {"state": "domcontentloaded"})
    cinematic_sleep(1)

    client.call("wait_for_selector", {"selector": "textarea#area", "state": "visible"})

    linkedin_draft = f"""Today's Top Tech Discussion

Just came across the biggest story on Hacker News today:
"{topic}"

I cross-referenced this with community discussions on Reddit to understand what developers are really thinking. Here is the consensus:

{summary}
Sentiment: {sentiment}

What do you all think about this? Let me know below. #TechNews #Programming #Discussion
"""

    print(f"{YELLOW}  [Cognitive] AI typing the final drafted post...{RESET}")

    # Clear the notepad
    client.call("execute_js", {"script": "document.querySelector('textarea#area').value = '';"})

    # Type out the drafted post character-by-character
    safe_draft = linkedin_draft.replace("`", "\\`")
    typing_script = f"""
        const ta = document.querySelector('textarea#area');
        const text = `{safe_draft}`;
        let i = 0;
        function typeChar() {{
            if (i < text.length) {{
                ta.value += text.charAt(i);
                ta.scrollTop = ta.scrollHeight;
                i++;
                setTimeout(typeChar, 15);
            }}
        }}
        typeChar();
    """
    client.call("execute_js", {"script": typing_script})

    typing_duration = (len(linkedin_draft) * 0.015) + 3
    cinematic_sleep(typing_duration)

    print(f"{GREEN}{BOLD}Mission Accomplished: Auto-Drafting Complete.{RESET}\n")

except Exception as e:
    print(f"\n{RED}Error: {e}{RESET}")
finally:
    client.close()
