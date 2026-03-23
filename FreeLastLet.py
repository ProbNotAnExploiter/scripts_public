#this script isnt fully completed so you may encounter some bugs while playing, thanks
import tkinter as tk
from tkinter import messagebox, ttk
import random
import requests
import pickle
import os
from collections import defaultdict
import string
from PIL import ImageGrab, Image, ImageTk, ImageFilter


MAX_PREFIX = 4
MIN_PREFIX = 1
CACHE_FILE = "referenceletter_cache.pkl"
BG = "#0f172a"
CARD = "#1e293b"
ACCENT = "#38bdf8"
TEXT = "#e2e8f0"
BTN = "#334155"
BTN_HOVER = "#475569"
WARNING_BG = "#dc2626"
WARNING_TEXT = "#fef2f2"
Game_state = "mainmenu"
DIFFICULTY = ["easy", "medium", "hard", "extreme"]
TRIES_PER_TURN = 5

TIMER_MIN = 2
TIMER_MAX = 50

URLS = [
    "https://raw.githubusercontent.com/ProbNotAnExploiter/wordies/refs/heads/main/old_skrylor",
]

impossible_urls = [
    "https://raw.githubusercontent.com/ProbNotAnExploiter/wordies/main/2letterstraps",
    "https://raw.githubusercontent.com/ProbNotAnExploiter/wordies/main/3kimpossiblewords4letters",
    "https://raw.githubusercontent.com/ProbNotAnExploiter/wordies/main/3letterstrap"
]

VOWELS = "ioaey"


def load_words():
    words = set()
    for url in URLS:
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            words.update(w.strip().lower() for w in r.text.splitlines() if w.strip())
        except:
            pass
    return words


def build_cache():
    words = load_words()
    prefix_map = defaultdict(list)
    for w in words:
        for i in range(1, min(MAX_PREFIX, len(w)) + 1):
            prefix_map[w[:i]].append(w)
    cache = {"words": words, "prefix_map": dict(prefix_map)}
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(cache, f)
    return cache


def load_cache():
    if not os.path.exists(CACHE_FILE):
        return build_cache()
    try:
        with open(CACHE_FILE, "rb") as f:
            return pickle.load(f)
    except:
        return build_cache()


cache = load_cache()
words = cache["words"]
prefix_map = cache["prefix_map"]
used = set()


def valid(prefix):
    return [w for w in prefix_map.get(prefix, []) if w not in used]


def load_TRAPS():
    TRAPS_2, TRAPS_3, TRAPS_4 = set(), set(), set()

    url_map = [
        (impossible_urls[0], TRAPS_2),
        (impossible_urls[1], TRAPS_3),
        (impossible_urls[2], TRAPS_4),
    ]

    for url, target_set in url_map:
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()

            for w in r.text.splitlines():
                w = w.strip().lower().replace(" ", "")
                if w:
                    target_set.add(w)

        except:
            pass

    return TRAPS_2, TRAPS_3, TRAPS_4


TRAPS_2, TRAPS_3, TRAPS_4 = load_TRAPS()


def trap_penalty(word):
    word = word.lower()
    penalty = 1.0
    if len(word) >= 2 and word[-2:] in TRAPS_2:
        penalty *= 0.6
    if len(word) >= 3 and word[-3:] in TRAPS_3:
        penalty *= 0.4
    if len(word) >= 4 and word[-4:] in TRAPS_4:
        penalty *= 0.2
    return penalty


def weighted_choice(choices):
    total = sum(w for _, w in choices)
    r = random.uniform(0, total)
    upto = 0
    for item, w in choices:
        upto += w
        if r <= upto:
            return item
    return choices[-1][0]


def bot_move(prefix):
    opts = valid(prefix)
    if not opts:
        return None

    weighted = []
    for w in opts:
        weight = trap_penalty(w)
        if weight > 0:
            weighted.append((w, weight))

    return weighted_choice(weighted) if weighted else random.choice(opts)


def find_nearest_playable_suffix(word, max_len=MAX_PREFIX):
    word = word.lower().strip()

    while len(word) > 1 and word[-1] == word[-2]:
        word = word[:-1]

    for length in range(min(max_len, len(word)), 0, -1):
        candidate = word[-length:]

        if len(candidate) == 2 and candidate[1] == 's' and candidate[0] not in VOWELS:
            continue

        if candidate in prefix_map:
            return candidate

    return word[-1:]


class App:
    def __init__(self, root):
        self.ability_cooldowns = {
            "skipper": 3000,
            "+7s": 5000,
            "finisher": 10000,
            "library of babel": 7000
            }

        self.ability_last_used = {ability: 0 for ability in self.ability_cooldowns}
        self.current_word = ""
        self.root = root
        self.root.title("Last letter - Free version")
        self.root.configure(bg=BG)
        self.root.geometry("520x700")
        self._locked = False
        self.mode = tk.StringVar(value="bot")
        self.difficulty = tk.StringVar(value="medium")
        self.timer_setting = tk.IntVar(value=15)

        self.container = tk.Frame(root, bg=BG)
        self.container.pack(expand=True, fill="both")
        self.paused = False
        self.slow_factor = 1.0
        self.slow_job = None
        self.overlay = None

        self.error_notification_frame = tk.Frame(root, bg="#dc2626", height=50)
        self.error_notification_frame.place(relx=0, rely=0, anchor="nw", relwidth=1)
        self.error_notification_frame.place_forget()

        self.error_notification_label = tk.Label(
            self.error_notification_frame,
            text="",
            bg="#dc2626",
            fg="#fef2f2",
            font=("Segoe UI", 13, "bold"),
            wraplength=460
        )
        self.error_notification_label.pack(side="left", padx=20, pady=12, fill="x", expand=True)

        self.error_close_btn = tk.Label(
            self.error_notification_frame,
            text="×",
            bg="#dc2626",
            fg="#fef2f2",
            font=("Segoe UI", 18, "bold"),
            cursor="hand2",
            padx=12
        )
        self.error_close_btn.pack(side="right", padx=10)
        self.error_close_btn.bind("<Button-1>", lambda e: self.hide_error())

        self.success_notification_frame = tk.Frame(root, bg="#0DFF00", height=50)
        self.success_notification_frame.place(relx=0, rely=0, anchor="nw", relwidth=1)
        self.success_notification_frame.place_forget()

        self.success_notification_label = tk.Label(
            self.success_notification_frame,
            text="",
            bg="#0DFF00",
            fg="#000000",
            font=("Segoe UI", 13, "bold"),
            wraplength=460
        )
        self.success_notification_label.pack(side="left", padx=20, pady=12, fill="x", expand=True)

        self.success_close_btn = tk.Label(
            self.success_notification_frame,
            text="×",
            bg="#0DFF00",
            fg="#ecfdf5",
            font=("Segoe UI", 18, "bold"),
            cursor="hand2",
            padx=12
        )
        self.success_close_btn.pack(side="right", padx=10)
        self.success_close_btn.bind("<Button-1>", lambda e: self.hide_success())
        
        self.root.bind("<Return>", self.handle_enter)
        self.root.bind("<Escape>", self.toggle_pause)

        self.quest_words = []
        self.strikethrough_words = set()
        self.space_locked = False
        self.current_ability_index = 0

        self.ability_label = tk.Label(self.root, text="Ability: skipper", 
                                      font=("Segoe UI", 12, "bold"), bg=BG, fg=ACCENT)
        self.ability_label.place(relx=0.5, rely=0.95, anchor="s")

        self.main_menu()


    def update_ability_display(self):
        self.ability_label.config(text=f"Ability: {self.abilities[self.current_ability_index]}")

    def prev_ability(self, event=None):
        self.current_ability_index = (self.current_ability_index - 1) % len(self.abilities)
        self.update_ability_display()
        return "break"

    def next_ability(self, event=None):
        self.current_ability_index = (self.current_ability_index + 1) % len(self.abilities)
        self.update_ability_display()
        return "break"


    def show_notification(self, message, duration=2800, level="info"):
            self.show_error_notification(message, duration)
    def show_success(self, message, duration=2800, level="info"):
            self.show_success_notification(message, duration)

    def show_error_notification(self, message, duration=2800):
        self.error_notification_label.config(text=message)
        self.error_notification_frame.place(relx=0.5, rely=0, anchor="n", relwidth=1)
        self.error_notification_frame.lift()
        self.root.after(duration, self.hide_error_notification)

    def hide_error_notification(self):
        self.error_notification_frame.place_forget()

    def show_success_notification(self, message, duration=2800):
        self.success_notification_label.config(text=message)
        self.success_notification_frame.place(relx=0.5, rely=0, anchor="n", relwidth=1)
        self.success_notification_frame.lift()
        self.root.after(duration, self.hide_success_notification)

    def hide_success_notification(self):
        self.success_notification_frame.place_forget()

    def hide_error(self):
        self.error_notification_frame.place_forget()

    def hide_success(self):
        self.success_notification_frame.place_forget()


    def clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def card(self):
        frame = tk.Frame(self.container, bg=CARD, padx=40, pady=40)
        frame.place(relx=0.5, rely=0.5, anchor="center")
        return frame

    def big_button(self, parent, text, cmd):
        btn = tk.Label(
            parent,
            text=text,
            bg=BTN,
            fg=TEXT,
            font=("Segoe UI", 16),
            padx=25,
            pady=15,
            cursor="hand2"
        )
        btn.pack(fill="x", pady=10)
        btn.bind("<Button-1>", lambda e: cmd())
        btn.bind("<Enter>", lambda e: btn.config(bg=BTN_HOVER))
        btn.bind("<Leave>", lambda e: btn.config(bg=BTN))

    def flat_dropdown(self, parent, variable, options):
        wrapper = tk.Frame(parent, bg=CARD)
        wrapper.pack(fill="x", pady=10)
        display = tk.Label(
            wrapper,
            text=f"{str(variable.get()).capitalize()} ▼",
            bg=BTN,
            fg=TEXT,
            font=("Segoe UI", 16),
            padx=20,
            pady=15,
            anchor="w",
            cursor="hand2"
        )
        display.pack(fill="x")

        dropdown = tk.Frame(wrapper, bg=CARD)

        def toggle():
            if dropdown.winfo_ismapped():
                dropdown.pack_forget()
            else:
                dropdown.pack(fill="x")

        def select(opt):
            variable.set(opt)
            display.config(text=f"{str(opt).capitalize()} ▼")
            dropdown.pack_forget()

        display.bind("<Button-1>", lambda e: toggle())
        for opt in options:
            item = tk.Label(
                dropdown,
                text=str(opt).capitalize(),
                bg=BTN,
                fg=TEXT,
                font=("Segoe UI", 14),
                padx=20,
                pady=10,
                anchor="w",
                cursor="hand2"
            )
            item.pack(fill="x")
            item.bind("<Button-1>", lambda e, o=opt: select(o))
            item.bind("<Enter>", lambda e, w=item: w.config(bg=BTN_HOVER))
            item.bind("<Leave>", lambda e, w=item: w.config(bg=BTN))
        return wrapper

    def slider(self, parent, variable, min_val, max_val):
        wrapper = tk.Frame(parent, bg=CARD)
        wrapper.pack(fill="x", pady=10)
        value_label = tk.Label(
            wrapper,
            text=f"{variable.get()}s",
            font=("Segoe UI", 16, "bold"),
            bg=CARD,
            fg=ACCENT
        )
        value_label.pack(pady=(0, 5))

        scale = tk.Scale(
            wrapper,
            from_=min_val,
            to=max_val,
            orient="horizontal",
            variable=variable,
            showvalue=0,
            bg=CARD,
            fg=TEXT,
            troughcolor=BTN,
            highlightthickness=0,
            activebackground=ACCENT,
            length=300,
            bd=0,
            relief="flat",
            sliderrelief="flat"
        )
        scale.pack()

        def update(val):
            value_label.config(text=f"{int(float(val))}s")

        scale.config(command=update)
        return wrapper


    def main_menu(self):
        global Game_state
        Game_state = "mainmenu"
        if hasattr(self, 'entry'):
            self.entry = None
        self.clear()
        frame = self.card()
        tk.Label(frame, text="Reference Letter", font=("Segoe UI", 28, "bold"),
                 bg=CARD, fg=TEXT).pack(pady=20)
        self.big_button(frame, "Play", self.mode_menu)
        self.big_button(frame, "Exit", self.root.quit)

    def mode_menu(self):
        global Game_state
        Game_state = "choose_mode"
        if hasattr(self, 'entry'):
            self.entry = None
        self.clear()
        frame = self.card()
        tk.Label(frame, text="Select a mode", font=("Segoe UI", 20),
                 bg=CARD, fg=TEXT).pack(pady=10)
        self.big_button(frame, "Bot", lambda: self.settings_menu("bot"))
        self.big_button(frame, "Yourself", lambda: self.settings_menu("self"))

    def settings_menu(self, mode):
        global Game_state
        Game_state = "settings"
        self.mode.set(mode)
        self.clear()
        frame = self.card()
        tk.Label(frame, text="Settings", font=("Segoe UI", 22),
                 bg=CARD, fg=TEXT).pack(pady=10)

        if mode == "bot":
            tk.Label(frame, text="Difficulty", font=("Segoe UI", 14),
                     bg=CARD, fg=TEXT).pack()
            self.flat_dropdown(frame, self.difficulty, DIFFICULTY)

        tk.Label(frame, text="set your time.", font=("Segoe UI", 14),
                 bg=CARD, fg=TEXT).pack()
        self.slider(frame, self.timer_setting, TIMER_MIN, TIMER_MAX)
        self.big_button(frame, "Start Game", self.start_game)


    def start_game(self):
        global Game_state
        Game_state = "playing"
        used.clear()
        self.player_lives = 3
        self.time_limit = self.timer_setting.get()
        self.time_left = self.time_limit
        self.timer_job = None
        self.abilities = ["skipper", "+7s", "finisher", "library of babel"]
        self.tries_left = TRIES_PER_TURN
        self.turn_count = 0
        self.player_word = ""

        self.assign_random_traps()
        

        self.prefix = random.choice([l for l in string.ascii_lowercase if l in prefix_map])

        self.clear()
        frame = self.card()

        self.log_frame = tk.Frame(
            self.root,
            bg=BG,
            bd=0,
            relief="flat"
        )
        self.log_frame.place(relx=0, rely=0, anchor="nw", width=380, relheight=1)

        log_header = tk.Label(
            self.log_frame,
            text="Match logs",
            font=("Consolas", 12, "bold"),
            bg=BG,
            fg="#FFFFFF",
            pady=10
        )
        log_header.pack(fill="x")

        self.log_text = tk.Text(
            self.log_frame,
            bg=BG,
            fg="#FFF7F7",
            font=("Consolas", 13),
            wrap="word",
            bd=0,
            highlightthickness=0,
            insertbackground="#0DFF00"
        )
        self.log_text.pack(fill="both", expand=True)
        self.log_text.config(padx=10, pady=10)


        self.quest_frame = tk.Frame(self.root, bg=BG, bd=0, highlightthickness=0)
        self.quest_frame.place(relx=1, rely=0, anchor="ne", width=280, height=160)

        header = tk.Label(self.quest_frame, text="traps u need to try", font=("Arial", 14, "bold"), bg=BG, fg=TEXT, pady=6)
        header.pack(fill="x")

        
        self.quest_display = tk.Text(
            self.quest_frame,
            bg=BG,
            fg=TEXT,
            font=("Arial", 11),
            wrap="word",
            padx=10,
            pady=12,
            height=6,        
            bd=0,
            highlightthickness=0
        )
        self.quest_display.pack(fill="both", expand=True)
        self.quest_display.config(state="disabled") 
        self.update_quest_display()
        self.bot_response_label = tk.Label(frame, text="Bot: None", font=("Segoe UI", 16, "bold"), 
                                         bg=CARD, fg=ACCENT, pady=8)
        self.bot_response_label.pack(pady=(20, 5))

        self.label = tk.Label(
            frame, text=self.prefix.upper(),
            font=("Segoe UI", 40, "bold"),
            bg=CARD, fg=ACCENT
        )
        self.label.pack(pady=10)

        self.entry = tk.Entry(frame, font=("Segoe UI", 18), justify="center", width=24)
        self.entry.pack(pady=6)
        self.entry.focus_set()
        self.entry.icursor(tk.END)

        tk.Label(
            frame,
            text="space = ability [] <> change ability",
            font=("Segoe UI", 11),
            bg=CARD,
            fg="#94a3b8",
        ).pack(pady=(0, 10))

        self.set_prefix()
        self.entry.bind("<KeyPress>", self.lock_prefix)
        self.entry.bind("<KeyPress-space>", self.on_space)
        self.root.bind("<Right>", self.greaterthing)
        self.root.bind("<Right>", self.nah, add="+")
        self.root.bind("<Left>", self.nahh)
        
        self.big_button(frame, "Submit", self.player_move)

        self.tries_label = tk.Label(
            frame,
            text=f"Tries: {self.tries_left}",
            font=("Segoe UI", 14),
            bg=CARD,
            fg=ACCENT
        )
        self.tries_label.pack()

        self.lives_label = tk.Label(
            frame,
            text=f"Lives: {self.player_lives}",
            font=("Segoe UI", 14),
            bg=CARD,
            fg="#f87171"
        )
        self.lives_label.pack()

        self.timer_label = tk.Label(frame, font=("Segoe UI", 14), bg=CARD, fg=TEXT)
        self.timer_label.pack()

        self.update_ability_display()
        self.run_timer()

    def update_quest_display(self):
        self.quest_display.config(state="normal")  
        self.quest_display.delete("1.0", "end")   

        if self.quest_words:
            display_words = []
            for w in self.quest_words:
                if w in self.strikethrough_words:
                    display_words.append(f"")
                else:
                    display_words.append(w)
            text = "  ".join(display_words)
        else:
            text = "No Traps"

        self.quest_display.insert("1.0", text)
        self.quest_display.config(state="disabled")



    def assign_random_traps(self):
        all_traps = list(TRAPS_2 | TRAPS_3 | TRAPS_4)
        if not all_traps:
            self.quest_words = []
            return
        num_traps = random.randint(1, min(5, len(all_traps)))
        self.quest_words = random.sample(all_traps, num_traps)
        self.strikethrough_words.clear()


    def reset_timer(self):
        if self.timer_job:
            self.root.after_cancel(self.timer_job)
        self.time_left = self.time_limit
        self.run_timer()


    def run_timer(self):
        try:
            self.timer_label.config(text=f"Time: {self.time_left}")
        except tk.TclError:
            return

        if self.slow_factor == 0:
            self.timer_job = self.root.after(100, self.run_timer)
            return

        if self.time_left <= 0:
            self.show_notification("Time out, bud")
            self.lose_life()
            return

        self.time_left -= 1

        delay = int(1000 / self.slow_factor)
        self.timer_job = self.root.after(delay, self.run_timer)


    def handle_enter(self, event):
        if hasattr(self, "entry") and self.entry.winfo_exists():
            self.player_move()
        return "break"


    def on_space(self, event):
        if self.space_locked:
            return "break"
        self.space_locked = True
        self.root.after(150, self.unlock_space)
        self.use_ability()
        return "break"


    def unlock_space(self):
        self.space_locked = False


    def lose_life(self):
        self.player_lives -= 1
        self.lives_label.config(text=f"Lives: {self.player_lives}")
        if self.player_lives <= 0:
            if hasattr(self, 'log_frame'):
                self.log_frame.destroy()
            if hasattr(self, 'quest_frame'):
                self.quest_frame.destroy()
            if hasattr(self, 'timer_job') and self.timer_job:
                self.root.after_cancel(self.timer_job)
            messagebox.showinfo("ez noob")
            self.main_menu()
            return
        self.tries_left = TRIES_PER_TURN
        self.tries_label.config(text=f"Tries: {self.tries_left}")
        self.turn_count = 0
        self.bot_response_label.config(text="Bot: None")
        self.assign_random_traps()
        self.prefix = self.get_dynamic_prefix(None)
        self.label.config(text=self.prefix.upper())
        self.set_prefix()
        self.reset_timer()


    def player_move(self):
        if self.slow_factor < 0.1:
            return
        if not hasattr(self, "entry"):
            return
        word = self.entry.get().lower().strip()
        self.current_word = word

        if word in used:
            self.show_notification("word used :wilted_rose:")
            return

        if word not in words or not word.startswith(self.prefix):
            self.tries_left -= 1
            self.tries_label.config(text=f"Tries: {self.tries_left}")
            if self.tries_left <= 0:
                self.lose_life()
            return

        used.add(word)

        if word in self.quest_words:
            self.strikethrough_words.add(word)
            self.update_quest_display()
        if self.mode.get() == "self":
            self.player_word = word 
            prefix = self.get_dynamic_prefix(word)  

            self.tries_left = TRIES_PER_TURN
            self.tries_label.config(text=f"Tries: {self.tries_left}")
            self.reset_timer()
            self.log_text.insert("end", f"Blud submitted; {word}\n")
            self.label.config(text=prefix.upper())
            self.bot_response_label.config(text=f"Blud: {word}")
            self.log_text.see("end")
        elif self.mode.get() == "bot":
            self.log_text.see("end")
            dynamic_prefix = self.get_dynamic_prefix(self.current_word, for_bot=True)
            bot_word = bot_move(dynamic_prefix)
            if not bot_word:
                self.log_text.insert("end", f"Blud yapped: {word} => Bot: ????\n")
                self.log_text.see("end")
                messagebox.showinfo("gg I guess bro")
                if hasattr(self, 'log_frame') and self.log_frame.winfo_exists():
                    self.log_frame.destroy()
                if hasattr(self, 'quest_frame') and self.quest_frame.winfo_exists():
                    self.quest_frame.destroy()
                if hasattr(self, 'timer_job') and self.timer_job:
                    self.root.after_cancel(self.timer_job)
                    self.timer_job = None
                self.main_menu()
                return
            self.bot_response_label.config(text=f"Bot: {bot_word}")
            self.log_text.insert("end", f"Blud yapped: {word} => Bot: {bot_word}\n")
            self.log_text.see("end")

            used.add(bot_word)

            self.prefix = self.get_dynamic_prefix(bot_word)
            self.label.config(text=self.prefix.upper())
            self.set_prefix()
            self.tries_left = TRIES_PER_TURN
            self.tries_label.config(text=f"Tries: {self.tries_left}")
            self.reset_timer()

    def use_ability(self):
        if self.slow_factor < 0.1:
            return
         
        current_prefix = self.entry.get().lower().strip() if hasattr(self, 'entry') else self.prefix

        ability = self.abilities[self.current_ability_index]
        if ability == "skipper":
            roll = random.random()

            if self.mode.get() == "bot":
                if roll <= 0.75:
                    last_word = self.current_word if self.current_word else self.prefix
                    log_word = self.prefix
                    bot_word = bot_move(self.prefix)
                    if bot_word:
                        used.add(bot_word)
                        self.prefix = self.get_dynamic_prefix(bot_word)
                        self.set_prefix()
                        self.tries_left = TRIES_PER_TURN
                        self.tries_label.config(text=f"Tries: {self.tries_left}")
                        self.reset_timer()
                        self.log_text.insert("end", f"Blud yapped: {log_word} => Bot: {bot_word}\n")
                        self.bot_response_label.config(text=f"Bot: {bot_word}")
                        self.label.config(text=self.prefix.upper())
                        self.log_text.see("end")
                else:
                    random_letter = random.choice(string.ascii_lowercase)
                    bot_word = bot_move(random_letter)
                    self.tries_left = TRIES_PER_TURN
                    self.prefix = self.get_dynamic_prefix(bot_word)
                    self.label.config(text=self.prefix.upper())
                    self.bot_response_label.config(text=f"Bot: {bot_word}")
                    self.tries_label.config(text=f"Tries: {self.tries_left}")
                    self.reset_timer()
                    self.log_text.insert("end", f"Blud yapped: ###### => Bot: {bot_word}\n")
                    self.log_text.see("end")
                    self.label.config(text=self.prefix.upper())
                    if bot_word:
                        used.add(bot_word)
                        self.prefix = self.get_dynamic_prefix(bot_word)
                        self.set_prefix()
            else:  
                if roll <= 0.75:
                    options = [w for w in valid(current_prefix) if w.startswith(current_prefix)]
                    if options:
                        solve_word = random.choice(options)
                        self.bot_response_label.config(text= f"Blud yapped: {self.prefix}")
                        self.entry.delete(0, tk.END)
                        self.entry.insert(0, solve_word)
                        self.log_text.see("end")
                    
                        new_prefix = self.get_dynamic_prefix(solve_word)
                        self.prefix = new_prefix
                        self.set_prefix()
                        self.label.config(text=self.prefix) 
                        self.tries_left = TRIES_PER_TURN
                        self.tries_label.config(text=f"Tries: {self.tries_left}")
                        self.reset_timer()
                        self.log_text.insert("end", f"the solve for {current_prefix} is {solve_word} Btw\n")

                        self.log_text.see("end")
                    else:
                        random_prefix = random.choice(string.ascii_lowercase)
                        self.bot_response_label.config(text= f"Blud yapped: {self.prefix}")
                        self.prefix = random_prefix
                        self.set_prefix()
                        self.tries_left = TRIES_PER_TURN
                        self.tries_label.config(text=f"Tries: {self.tries_left}")
                        self.reset_timer()
                        self.log_text.see("end")
                        self.label.config(text=current_prefix)
                        self.bot_response_label.config(text= f"Blud yapped: #######")
                        self.label.config(text=self.prefix) 
                        self.log_text.insert("end", f"i dont have the solve for {self.prefix} \n")
                        self.log_text.insert("end", f"skipped, heres yo new prefix {random_prefix}\n")
                        self.log_text.see("end")
                else:
                    random_prefix = random.choice(string.ascii_lowercase)
                    self.prefix = random_prefix
                    self.set_prefix()
                    self.tries_left = TRIES_PER_TURN
                    self.tries_label.config(text=f"Tries: {self.tries_left}")
                    self.reset_timer()
                    self.bot_response_label.config(text= f"Blud yapped: #######")
                    self.log_text.insert("end", f"heres yo new prefix:{random_prefix}\n")
                    self.label.config(text=random_prefix) 
                    self.log_text.see("end")
        elif ability == "+7s":
            self.time_left += 7
        elif ability == "finisher":
            self.show_notification("i didnt code this")
        elif ability == "library of babel":
            options = [w for w in valid(current_prefix) if w.startswith(current_prefix)]
    
            if options:
                complete_word = random.choice(options)
        
                self.entry.delete(0, tk.END)
                self.entry.insert(0, complete_word)
            else:
                self.show_notification("too smart but not too dumb", 2000)


    def get_dynamic_prefix(self, last_word, for_bot=False):
        self.turn_count += 1
        if self.turn_count <= 5:
            lengths = [1]
            weights = [100]
        elif self.turn_count <= 10:
            lengths = [1, 2]
            weights = [40, 60]
        elif self.turn_count <= 15:
            lengths = [1, 2, 3]
            weights = [50, 30, 20]
        else:
            lengths = [1, 2, 3, 4]
            weights = [30, 30, 25, 15]

        source_word = (last_word or getattr(self, 'player_word', ""))

        if source_word:
       
            suffix = source_word[-4:] if len(source_word) >= 4 else source_word
            valid_lengths = [l for l in lengths if l <= len(suffix)]
            ignored_weight = sum(w for l, w in zip(lengths, weights) if l > len(suffix))

            if valid_lengths and ignored_weight > 0:
                redistributed_weight = ignored_weight / len(valid_lengths)
                valid_weights = [w + redistributed_weight for l, w in zip(lengths, weights) if l <= len(suffix)]
            else:
                valid_weights = [w for l, w in zip(lengths, weights) if l <= len(suffix)]

            length = random.choices(valid_lengths, weights=valid_weights)[0]
            prefix = suffix[-length:]
        else:
            prefix = random.choice(string.ascii_lowercase)
        if not for_bot:
            self.prefix = prefix
            self.set_prefix()
            if self.mode.get() == "self":
                self.tries_left = TRIES_PER_TURN
                self.tries_label.config(text=f"Tries: {self.tries_left}")
                self.reset_timer()

        return prefix


    def set_prefix(self):
        self.entry.delete(0, tk.END)
        self.entry.insert(0, self.prefix)
        self.entry.focus_set()
        self.entry.icursor(tk.END)


    def lock_prefix(self, event):
        if event.keysym in ["BackSpace", "Delete"]:
            if self.entry.index(tk.INSERT) <= len(self.prefix):
                return "break"
        if event.keysym == "space":
            return "break"
    def greaterthing(self, event=None):
        if self._locked:
            return "break"
        self._locked = True
        self.next_ability()
        self.root.after(200, self.unlock_lock)  

    def unlock_lock(self):
        self._locked = False
    def lessthing(self, event=None):
        if self._locked:
            return "break"
        self._locked = True
        self.prev_ability()
        self.root.after(200, self.unlock_lock) 
        return "break"
            
        

    def toggle_pause(self, event=None):
        global Game_state
        if Game_state == "playing":
            if not self.paused:
                self.paused = True
                self.slow_factor = 0.2
                self.show_overlay()
            else:
                self.paused = False
                self.slow_factor = 1.0
                self.hide_overlay()
        elif Game_state == "choose_mode":
            self.main_menu()
            Game_state = "mainmenu"
        elif Game_state == "settings":
            self.mode_menu()
            Game_state = "choose_mode"


    def show_overlay(self):
        img = self.capture_gui()
        blurred = self.blur_image(img)

        self.blurred_tk = ImageTk.PhotoImage(blurred)

        self.overlay = tk.Label(self.root, image=self.blurred_tk)
        self.overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.overlay.lift()


    def hide_overlay(self):
        if self.overlay:
            self.overlay.destroy()
            self.overlay = None

    def nah(self, event=None):
        if hasattr(self, "entry") and self.entry:
            self.entry.icursor(tk.END)
        return None
    def nahh(self, event=None):
        self.lessthing()
        if hasattr(self, "entry") and self.entry:
            self.entry.icursor(tk.END)
        return None


    def capture_gui(self):
        x = self.root.winfo_rootx()
        y = self.root.winfo_rooty()
        w = x + self.root.winfo_width()
        h = y + self.root.winfo_height()
    
        img = ImageGrab.grab(bbox=(x, y, w, h))
        return img
    

    def blur_image(self, img, radius=8):
        return img.filter(ImageFilter.GaussianBlur(radius))


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()

