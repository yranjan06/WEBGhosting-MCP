#!/usr/bin/env python3
"""
WEBGhosting Terminal UI — Zero-dependency professional CLI rendering.

Uses Unicode box-drawing characters + ANSI colors for a premium look.
No external libraries required.
"""

import sys, os, time, threading, shutil

# ━━━ ANSI Colors (Extended) ━━━
class C:
    """Extended ANSI color codes for premium terminal rendering."""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    ITALIC  = "\033[3m"
    UNDER   = "\033[4m"
    
    # Foreground
    BLACK   = "\033[30m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    
    # Bright Foreground
    BRED    = "\033[91m"
    BGREEN  = "\033[92m"
    BYELLOW = "\033[93m"
    BBLUE   = "\033[94m"
    BMAGENTA= "\033[95m"
    BCYAN   = "\033[96m"
    BWHITE  = "\033[97m"
    
    # Background
    BG_BLACK  = "\033[40m"
    BG_BLUE   = "\033[44m"
    BG_CYAN   = "\033[46m"
    BG_GREEN  = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_RED    = "\033[41m"
    BG_MAGENTA= "\033[45m"

# Box-drawing characters
BOX_TL = "╭"
BOX_TR = "╮"
BOX_BL = "╰"
BOX_BR = "╯"
BOX_H  = "─"
BOX_V  = "│"
BOX_LT = "├"
BOX_RT = "┤"
CHECK  = "»"
CROSS  = "x"
GEAR   = "*"
BOLT   = "»"
GLOBE  = "O"
LOCK   = "#"
BRAIN  = "»"
ROCKET = "»"
PKG    = "+"
MAG    = "»"
CLOCK  = "@"

def _term_width():
    """Get terminal width, default 80."""
    try:
        return shutil.get_terminal_size().columns
    except:
        return 80


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Box / Panel
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def panel(title, lines, color=C.CYAN, width=None):
    """Render a boxed panel with title and content lines."""
    w = width or max(60, _term_width() - 4)
    inner = w - 2
    
    # Title line
    t = f" {title} "
    t_vis = len(_strip_ansi(t))
    pad = max(0, inner - t_vis - 1)
    top = f"  {color}{BOX_TL}{BOX_H}{C.BOLD}{t}{C.RESET}{color}{BOX_H * pad}{BOX_TR}{C.RESET}"
    print(top)
    
    for line in lines:
        vis = _strip_ansi(line)
        if len(vis) > inner - 1:
            line = _truncate_ansi(line, inner - 4) + f"{C.RESET}..."
            vis = _strip_ansi(line)
            
        padding = max(0, inner - len(vis) - 1)
        print(f"  {color}{BOX_V}{C.RESET} {line}{' ' * padding}{color}{BOX_V}{C.RESET}")
    
    bottom = f"  {color}{BOX_BL}{BOX_H * inner}{BOX_BR}{C.RESET}"
    print(bottom)


def divider(char="─", color=C.DIM, width=None):
    """Print a horizontal divider."""
    w = width or max(50, _term_width() - 4)
    print(f"  {color}{char * w}{C.RESET}")


def _strip_ansi(text):
    """Remove ANSI escape codes for length calculation."""
    import re
    return re.sub(r'\033\[[0-9;]*m', '', text)


def _truncate_ansi(text, max_len):
    """Truncate text to max_len visible chars, maintaining ANSI."""
    import re
    ansi_escape = re.compile(r'(\033\[[0-9;]*m)')
    parts = ansi_escape.split(text)
    vis_len = 0
    res = ""
    for p in parts:
        if ansi_escape.match(p):
            res += p
        else:
            if vis_len + len(p) <= max_len:
                res += p
                vis_len += len(p)
            else:
                rem = max_len - vis_len
                if rem > 0:
                    res += p[:rem]
                res += C.RESET
                break
    return res


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Table
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def table(headers, rows, color=C.CYAN):
    """Render a formatted table with headers and rows."""
    if not rows:
        return
    
    # Calculate column widths
    all_data = [headers] + rows
    col_widths = []
    for col_idx in range(len(headers)):
        max_w = max(len(str(row[col_idx])) for row in all_data if col_idx < len(row))
        col_widths.append(min(max_w + 2, 40))
    
    total_w = sum(col_widths) + len(col_widths) + 1
    
    # Top border
    top_line = f"  {color}{BOX_TL}" + "┬".join(BOX_H * w for w in col_widths) + f"{BOX_TR}{C.RESET}"
    print(top_line)
    
    # Header
    header_cells = []
    for i, h in enumerate(headers):
        header_cells.append(f"{C.BOLD}{str(h).center(col_widths[i])}{C.RESET}{color}")
    print(f"  {color}{BOX_V}" + f"{BOX_V}".join(header_cells) + f"{BOX_V}{C.RESET}")
    
    # Header separator
    sep_line = f"  {color}{BOX_LT}" + "┼".join(BOX_H * w for w in col_widths) + f"{BOX_RT}{C.RESET}"
    print(sep_line)
    
    # Data rows
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            if i < len(col_widths):
                cell_str = str(cell)
                if len(cell_str) > col_widths[i] - 2:
                    cell_str = cell_str[:col_widths[i] - 4] + ".."
                cells.append(f" {cell_str.ljust(col_widths[i] - 1)}")
        print(f"  {color}{BOX_V}{C.RESET}" + f"{color}{BOX_V}{C.RESET}".join(cells) + f"{color}{BOX_V}{C.RESET}")
    
    # Bottom border
    bot_line = f"  {color}{BOX_BL}" + "┴".join(BOX_H * w for w in col_widths) + f"{BOX_BR}{C.RESET}"
    print(bot_line)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Progress / Spinner  
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Spinner:
    """Animated terminal spinner for long operations."""
    
    # Simple brackets instead of dots to be more universally supported and clean
    FRAMES = ["[-]", "[\\]", "[|]", "[/]"]
    
    def __init__(self, message, color=C.CYAN):
        self._message = message
        self.color = color
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
    
    def update(self, message):
        with self._lock:
            self._message = message

    def _get_message(self):
        with self._lock:
            return self._message
    
    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self
    
    def _spin(self):
        i = 0
        while self._running:
            frame = self.FRAMES[i % len(self.FRAMES)]
            msg = self._get_message()
            
            # Responsive truncation
            w = _term_width() - 10
            if len(_strip_ansi(msg)) > w:
                msg = msg[:w-3] + "..."
                
            sys.stdout.write(f"\r  {self.color}{frame}{C.RESET} {msg}                    ")
            sys.stdout.flush()
            time.sleep(0.15)
            i += 1
            
    def _clear_line(self):
        sys.stdout.write("\r" + " " * (_term_width() - 1) + "\r")
    
    def stop(self, final_message=None):
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
        self._clear_line()
        msg = final_message or self._get_message()
        sys.stdout.write(f"  {C.GREEN}[ON]{C.RESET} {msg}\n")
        sys.stdout.flush()
    
    def fail(self, final_message=None):
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
        self._clear_line()
        msg = final_message or self._get_message()
        sys.stdout.write(f"  {C.RED}[FAIL]{C.RESET} {msg}\n")
        sys.stdout.flush()
    
    def __enter__(self):
        return self.start()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._running:
            if exc_type is not None:
                self.fail()
            else:
                self.stop()


def progress_bar(current, total, width=30, label="", color=C.CYAN):
    """Render an inline progress bar."""
    pct = current / max(total, 1)
    filled = int(width * pct)
    bar = f"{color}{'█' * filled}{C.DIM}{'░' * (width - filled)}{C.RESET}"
    sys.stdout.write(f"\r  {bar} {C.BOLD}{current}/{total}{C.RESET} {label}    ")
    sys.stdout.flush()
    if current >= total:
        print()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step Logger
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def step_header(step_num, total_steps, action, description):
    """Render a step execution header with progress."""
    pct = int((step_num / max(total_steps, 1)) * 100)
    badge = f"{C.BG_BLUE}{C.WHITE}{C.BOLD} {step_num}/{total_steps} {C.RESET}"
    act_badge = f"{C.CYAN}{C.BOLD}{action.upper()}{C.RESET}"
    print(f"\n  {badge} {act_badge} {C.DIM}{description}{C.RESET}  [{pct}%]")


def step_result(key, value, is_success=True):
    """Render a step result."""
    icon = f"{C.GREEN}{CHECK}" if is_success else f"{C.RED}{CROSS}"
    print(f"  {icon}{C.RESET} {C.DIM}{key}:{C.RESET} {C.WHITE}{value}{C.RESET}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Summary / Stats
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def stats_summary(token_usage, elapsed_seconds, steps_done, recipe_name=""):
    """Render end-of-run statistics panel."""
    total_tokens = sum(v for k, v in token_usage.items() if k != "calls")
    calls = token_usage.get("calls", 0)
    
    print()
    panel(f"{BOLT} Run Statistics", [
        f"{C.BOLD}Recipe:{C.RESET}     {recipe_name}",
        f"{C.BOLD}Steps:{C.RESET}      {steps_done} completed",
        f"{C.BOLD}Duration:{C.RESET}   {elapsed_seconds:.1f}s",
        f"",
        f"{C.BOLD}LLM Calls:{C.RESET}  {calls}",
        f"{C.BOLD}Tokens In:{C.RESET}  {token_usage.get('reframe_in', 0) + token_usage.get('recipe_in', 0):,}",
        f"{C.BOLD}Tokens Out:{C.RESET} {token_usage.get('reframe_out', 0) + token_usage.get('recipe_out', 0):,}",
        f"{C.BOLD}Total:{C.RESET}      {total_tokens:,} tokens",
    ], color=C.MAGENTA)


def pipeline_banner(prompt, reframed, domains, example_file, selectors_count):
    """Show the preprocessing pipeline results in a clean panel."""
    lines = [
        f"{C.DIM}Prompt:{C.RESET}     {C.WHITE}{prompt}{C.RESET}",
    ]
    if reframed and reframed != prompt:
        lines.append(f"{C.DIM}Reframed:{C.RESET}   {C.BGREEN}{reframed}{C.RESET}")
    lines.append(f"{C.DIM}Domains:{C.RESET}    {C.BCYAN}{domains}{C.RESET}")
    lines.append(f"{C.DIM}Selectors:{C.RESET}  {C.WHITE}{selectors_count} injected{C.RESET}")
    if example_file:
        lines.append(f"{C.DIM}Example:{C.RESET}    {C.WHITE}{example_file}{C.RESET}")
    
    panel(f"{BRAIN} Pipeline", lines, color=C.BLUE)


def recipe_banner(name, step_count):
    """Show recipe info before execution."""
    lines = [
        f"{C.BOLD}Name:{C.RESET}   {C.BCYAN}{name}{C.RESET}",
        f"{C.BOLD}Steps:{C.RESET}  {C.WHITE}{step_count}{C.RESET}",
    ]
    panel(f"{ROCKET} Recipe Generated", lines, color=C.GREEN)


def results_panel(results_dict):
    """Show extracted results in a clean format."""
    if not results_dict:
        return
    
    print()
    lines = []
    for key, value in results_dict.items():
        if isinstance(value, (list, dict)):
            import json
            formatted = json.dumps(value, indent=2, ensure_ascii=False)
            lines.append(f"{C.BOLD}{key}:{C.RESET}")
            for fline in formatted.split('\n'):
                lines.append(f"  {C.WHITE}{fline}{C.RESET}")
        else:
            val_str = str(value)
            if len(val_str) > 50:
                val_str = val_str[:47] + "..."
            lines.append(f"{C.BOLD}{key}:{C.RESET} {C.WHITE}{val_str}{C.RESET}")
    
    panel(f"{MAG} Results", lines, color=C.YELLOW)


def error_msg(message):
    """Display an error message."""
    print(f"\n  {C.RED}{C.BOLD}{CROSS} ERROR:{C.RESET} {C.RED}{message}{C.RESET}\n")


def success_msg(message):
    """Display a success message."""
    print(f"\n  {C.GREEN}{C.BOLD}{CHECK} {message}{C.RESET}\n")


def warn_msg(message):
    """Display a warning message."""
    print(f"  {C.YELLOW}{C.BOLD}⚠ {message}{C.RESET}")


def info_msg(message):
    """Display an info message."""
    print(f"  {C.DIM}{BOLT} {message}{C.RESET}")
