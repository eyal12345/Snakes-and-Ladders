"""SnakesAndLaddersApp class: the Tkinter user interface."""

import math
import tkinter as tk
from tkinter import messagebox

from board import Board
from exceptions import GameOverError, MatchHistoryError, SnakesAndLaddersError
from computer_player import ComputerPlayer
from difficulty import Difficulty
from game import Game
from match_history import MatchHistory, Record
from start_toss import StartToss


class SnakesAndLaddersApp:
    """Main window: board canvas on the left, controls / dice / log on the right."""

    GRID = 10
    CELL = 60
    START_STRIP = 50
    ANIMATION_DELAY_MS = 110
    COMPUTER_DELAY_MS = 700
    RECORD_COLOR = "#546e7a"
    GOLD = "#b8860b"           # a record equal to the fewest steps the board allows
    GOLD_SELECTED = "#ffd54f"  # the same on a selected (blue) list row
    DICE_SIZE = 64
    # Player modes: key -> (label, humans, computers). Humans come first, then the AI rivals.
    MODES = {
        "ai1": ("1 AI Rival", 1, 1),
        "ai2": ("2 AI Rivals", 1, 2),
        "ai3": ("3 AI Rivals", 1, 3),
        "p2": ("2 Players", 2, 0),
        "p3": ("3 Players", 3, 0),
        "p4": ("4 Players", 4, 0),
    }
    DEFAULT_MODE = "ai1"

    SQUARE_COLORS = ("#fdf6e3", "#e3f2fd")
    LADDER_COLOR = "#8d6e63"
    SNAKE_COLORS = ("#2e7d32", "#6a1b9a", "#c62828", "#558b2f", "#ef6c00", "#00838f")
    TOKEN_OFFSETS = ((-0.2, -0.2), (0.2, -0.2), (-0.2, 0.2), (0.2, 0.2))
    PIP_LAYOUT = {
        1: [(0.5, 0.5)],
        2: [(0.25, 0.25), (0.75, 0.75)],
        3: [(0.25, 0.25), (0.5, 0.5), (0.75, 0.75)],
        4: [(0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)],
        5: [(0.25, 0.25), (0.75, 0.25), (0.5, 0.5), (0.25, 0.75), (0.75, 0.75)],
        6: [(0.25, 0.25), (0.75, 0.25), (0.25, 0.5), (0.75, 0.5), (0.25, 0.75), (0.75, 0.75)],
    }

    def __init__(self, root):
        self._root = root
        self._game = None
        self._after_id = None
        self._tokens = {}
        self._player_labels = []
        self._color_menus = []
        self._game_mode = None
        self._match_history = MatchHistory()
        self._map_id = None  # ID of the board currently on screen
        self._mode = tk.StringVar(value=self.DEFAULT_MODE)

        # One color choice per possible participant; the values are always all different.
        self._color_vars = [
            tk.StringVar(value=name) for name in list(Game.COLORS)[:Game.MAX_PLAYERS]
        ]
        self._previous_colors = [var.get() for var in self._color_vars]
        self._updating_colors = False
        for index, var in enumerate(self._color_vars):
            var.trace_add("write", lambda *_args, i=index: self._on_color_changed(i))
        self._mode.trace_add("write", lambda *_args: self._on_mode_changed())

        self._difficulty = tk.StringVar(value=Difficulty.MEDIUM.label)
        self._loading_saved_map = False  # set while History Matches switches the level
        self._difficulty.trace_add("write", lambda *_args: self._on_difficulty_changed())

        # One name per possible participant.
        self._names_mode = self._mode.get()
        self._name_entries = []
        self._name_vars = [
            tk.StringVar(value=self._default_name(self._names_mode, i))
            for i in range(Game.MAX_PLAYERS)
        ]
        for var in self._name_vars:
            var.trace_add("write", lambda *_args: self._on_name_changed())

        root.title("Snakes and Ladders")
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.exit_game)
        root.bind("<space>", self._on_space)

        self._summary_pending = False
        self._build_ui()
        self._build_start_menu()
        self._show_start_menu()  # no match until the player clicks New Game

    # ================================================================== layout
    @property
    def _board_pixels(self):
        return self.GRID * self.CELL

    def _build_ui(self):
        # The match screen (board + side panel); hidden while the start menu is shown.
        self._game_screen = tk.Frame(self._root)
        self._canvas = tk.Canvas(
            self._game_screen,
            width=self._board_pixels,
            height=self._board_pixels + self.START_STRIP,
            bg="white",
            highlightthickness=0,
        )
        self._canvas.grid(row=0, column=0, padx=10, pady=10)

        panel = tk.Frame(self._game_screen, padx=10, pady=10)
        panel.grid(row=0, column=1, sticky="ns")

        self._build_settings_window()

        button_style = {"width": 20, "font": ("Helvetica", 11, "bold")}
        tk.Button(panel, text="New Game", command=self.new_game, bg="#c8e6c9", **button_style).pack(
            pady=(0, 3)
        )
        tk.Button(panel, text="Reset Game", command=self.reset_game, bg="#ffe0b2", **button_style).pack(
            pady=3
        )
        tk.Button(panel, text="History Matches", command=self.open_history, bg="#d1c4e9",
                  **button_style).pack(pady=3)

        # Dice and turn indicator side by side to keep the panel short.
        turn_row = tk.Frame(panel)
        turn_row.pack(pady=4)  # not filled, so the dice + turn pair is centered
        self._dice_canvas = tk.Canvas(turn_row, width=self.DICE_SIZE, height=self.DICE_SIZE,
                                      highlightthickness=0)
        self._dice_canvas.pack(side="left")
        self._status = tk.Label(turn_row, text="", font=("Helvetica", 12, "bold"), wraplength=170)
        self._status.pack(side="left", padx=8)
        self._roll_button = tk.Button(
            panel, text="Roll Dice  (Space)", command=self.roll_dice, bg="#bbdefb",
            state="disabled", **button_style
        )
        self._roll_button.pack(pady=3)
        self._map_label = tk.Label(panel, text="", fg="#546e7a", font=("Consolas", 10, "bold"))
        self._map_label.pack()
        self._record_label = tk.Label(panel, text="", fg=self.RECORD_COLOR,
                                      font=("Consolas", 10, "bold"))
        self._record_label.pack()

        level_box = tk.LabelFrame(panel, text="Difficulty level", padx=8, pady=4)
        level_box.pack(fill="x", pady=(4, 0))
        self._level_label = tk.Label(level_box, text="")
        self._level_label.pack(side="left")
        self._layout_label = tk.Label(level_box, text="")
        self._layout_label.pack(side="right")

        self._players_frame = tk.LabelFrame(panel, text="Players", padx=8, pady=4)
        self._players_frame.pack(fill="x", pady=4)

        # Packed before the log so the expanding log never pushes it out.
        tk.Button(panel, text="Main Menu", command=self.back_to_menu, bg="#ffcdd2",
                  **button_style).pack(side="bottom", pady=(8, 0))

        log_frame = tk.LabelFrame(panel, text="Game log", padx=4, pady=4)
        log_frame.pack(fill="both", expand=True, pady=4)
        scrollbar = tk.Scrollbar(log_frame)
        scrollbar.pack(side="right", fill="y")
        self._log = tk.Listbox(log_frame, width=40, height=6, yscrollcommand=scrollbar.set)
        self._log.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self._log.yview)

    def _build_settings_window(self):
        """Players, difficulty and names & colors live in a window shown by the Settings button."""
        window = tk.Toplevel(self._root, padx=10, pady=10)
        window.title("Settings")
        window.resizable(False, False)
        window.transient(self._root)
        window.protocol("WM_DELETE_WINDOW", window.withdraw)
        window.withdraw()  # built once, hidden until Settings is clicked
        self._settings_window = window
        panel = window

        # Two sections sharing one variable, so picking an option in one clears the other.
        self._single_box = tk.LabelFrame(panel, text="Singleplayer", padx=8, pady=2)
        self._single_box.pack(fill="x")
        self._multi_box = tk.LabelFrame(panel, text="Multiplayer", padx=8, pady=2)
        self._multi_box.pack(fill="x", pady=(6, 0))
        self._mode_buttons = []
        columns = {self._single_box: 0, self._multi_box: 0}
        for key, (text, _humans, computers) in self.MODES.items():
            box = self._single_box if computers else self._multi_box
            button = tk.Radiobutton(box, text=text, value=key, variable=self._mode)
            button.grid(row=0, column=columns[box], sticky="w", padx=4)  # three per row
            columns[box] += 1
            self._mode_buttons.append(button)

        self._difficulty_box = tk.LabelFrame(panel, text="Difficulty", padx=8, pady=2)
        self._difficulty_box.pack(fill="x", pady=(6, 0))
        self._difficulty_buttons = []
        for column, level in enumerate(Difficulty):
            button = tk.Radiobutton(self._difficulty_box, text=level.label, value=level.label,
                                    variable=self._difficulty)
            button.grid(row=0, column=column, sticky="w", padx=4)
            self._difficulty_buttons.append(button)
        # One line of fixed width (fits the longest description) so switching levels
        # never resizes the Settings window.
        self._difficulty_info = tk.Label(self._difficulty_box, fg="#546e7a", width=47,
                                         anchor="w", font=("Helvetica", 8))
        self._difficulty_info.grid(row=1, column=0, columnspan=3, sticky="w")

        # Same three equal columns in every options section, so the choices line up.
        for box in (self._single_box, self._multi_box, self._difficulty_box):
            for column in range(3):
                box.columnconfigure(column, weight=1, uniform="options")
        self._show_difficulty_info()

        self._colors_frame = tk.LabelFrame(panel, text="Names & colors", padx=8, pady=4)
        self._colors_frame.pack(fill="x", pady=(6, 0))
        self._name_error = tk.Label(panel, text="", fg="#c62828", wraplength=260)
        self._name_error.pack()
        self._build_color_rows()

        tk.Button(panel, text="Close", width=12, command=window.withdraw).pack(pady=(6, 0))

    def open_settings(self):
        window = self._settings_window
        window.deiconify()
        window.lift()
        window.focus_set()

    # ================================================================== start menu
    def _build_start_menu(self):
        menu = tk.Frame(self._root, padx=60, pady=30, bg="#fdf6e3")
        self._start_menu = menu

        tk.Label(menu, text="Snakes & Ladders", font=("Helvetica", 30, "bold"),
                 fg="#2e7d32", bg="#fdf6e3").pack(pady=(0, 20))

        button_style = {"width": 22, "font": ("Helvetica", 13, "bold"), "pady": 4}
        tk.Button(menu, text="New Game", command=self.new_game, bg="#c8e6c9",
                  **button_style).pack(pady=5)
        tk.Button(menu, text="Settings", command=self.open_settings, bg="#cfd8dc",
                  **button_style).pack(pady=5)
        tk.Button(menu, text="History Matches", command=self.open_history, bg="#d1c4e9",
                  **button_style).pack(pady=5)
        tk.Button(menu, text="Exit", command=self.exit_game, bg="#ffcdd2",
                  **button_style).pack(pady=5)

        self._summary_box = tk.LabelFrame(menu, text="Current settings", padx=12, pady=8,
                                          font=("Helvetica", 10, "bold"), bg="#fdf6e3")
        self._summary_box.pack(fill="x", pady=(20, 0))

        # Refresh the summary whenever any setting changes.
        for var in [self._mode, self._difficulty, *self._name_vars, *self._color_vars]:
            var.trace_add("write", lambda *_args: self._schedule_summary())
        self._refresh_summary()

    def _schedule_summary(self):
        """Refresh once after the current change settles (one change can set several vars)."""
        if not self._summary_pending:
            self._summary_pending = True
            self._root.after_idle(self._refresh_summary)

    def _refresh_summary(self):
        self._summary_pending = False
        box = self._summary_box
        for widget in box.winfo_children():
            widget.destroy()
        bg = box.cget("bg")
        mode = self._mode.get()
        level = self._selected_difficulty()
        # Every widget below has a fixed size, so changing a setting never resizes the window.
        players = self.MODES[mode][0]
        if self.MODES[mode][2]:  # singleplayer: "<name> vs. N AI Rivals"
            players = f"{self._name_vars[0].get().strip() or '(no name)'} vs. {players}"
        tk.Label(box, text=f"Game mode:  {players}", bg=bg, width=40,
                 anchor="w").grid(row=0, column=0, columnspan=4, sticky="w")
        tk.Label(box, text=f"Difficulty:  {level.label}", bg=bg,
                 anchor="w").grid(row=1, column=0, columnspan=4, sticky="w")
        tk.Label(box, text=level.description, fg="#546e7a", bg=bg, font=("Helvetica", 8),
                 width=55, height=2, wraplength=330, justify="left", anchor="nw").grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(0, 4)
        )
        # Two players per row; unused slots stay blank so the box keeps two rows.
        count = self._participant_count(mode)
        for slot in range(Game.MAX_PLAYERS):
            row, column = 3 + slot // 2, (slot % 2) * 2
            if slot < count:
                swatch = {"bg": Game.color_code(self._color_vars[slot].get()), "relief": "solid"}
                name = self._name_vars[slot].get().strip() or "(no name)"
            else:
                swatch = {"bg": bg, "relief": "flat"}
                name = ""
            tk.Label(box, width=2, bd=1, **swatch).grid(row=row, column=column, padx=(0, 6), pady=2)
            tk.Label(box, text=name, bg=bg, width=16, anchor="w").grid(
                row=row, column=column + 1, sticky="w"
            )

    def _show_start_menu(self):
        self._game_screen.grid_remove()
        self._start_menu.grid(row=0, column=0)

    def _show_game_screen(self):
        self._start_menu.grid_remove()
        self._game_screen.grid(row=0, column=0)

    def back_to_menu(self):
        """Leave the match screen; an unfinished match is abandoned."""
        if self._game is not None and not self._confirm(
            "Main menu", "Are you sure you want to go back to the main menu?"
        ):
            return
        self._cancel_animation()
        self._game = None
        self._update_mode_lock()  # settings are editable again
        self._show_start_menu()

    # ================================================================== actions
    def new_game(self):
        """Start a new match with a freshly randomized board."""
        # Asked on the match screen only; from the start menu New Game starts right away.
        if self._game is not None and not self._confirm(
            "New game", "Are you sure you want to start a new game?"
        ):
            return
        if self._start_with_random_board():
            self._save_current_map()  # every New Game click stores its map right away

    def _start_with_random_board(self):
        try:
            board = Game.random_board(self._selected_difficulty(), size=self.GRID * self.GRID)
        except SnakesAndLaddersError as error:
            messagebox.showerror("Cannot start game", str(error))
            return False
        return self._start_game(board, self._match_history.new_id())

    def _selected_difficulty(self):
        return Difficulty.from_label(self._difficulty.get())

    def _show_difficulty_info(self):
        self._difficulty_info.config(text=self._selected_difficulty().description)

    def _on_difficulty_changed(self):
        """Difficulty changed (only possible while unlocked): new board with the level's layout."""
        self._show_difficulty_info()
        if self._loading_saved_map:
            return  # a saved map brings its own board; no random one for the level
        if self._game is not None and not self._game.in_progress:
            if self._start_with_random_board():
                self._save_current_map()  # choosing a level also stores its new map

    def reset_game(self):
        """Restart the current match on the same board with everyone back at the start."""
        if self._game is None:
            return
        if not self._confirm("Reset game", "Are you sure you want to reset the game?"):
            return
        self._cancel_animation()
        self._game.reset()
        self._run_toss()  # a new toss decides the order again

    def _on_space(self, event):
        if isinstance(event.widget, tk.Entry):
            return  # typing a space in a name box must not roll the dice
        self.roll_dice()

    def _on_mode_changed(self):
        """Player count changed (only possible while unlocked): rebuild the match on the same board."""
        new_mode = self._mode.get()
        # Names still at the previous mode's default follow the new mode's defaults
        # (e.g. "You"/"AI Rival" <-> "Player 1"/"Player 2"); custom names are kept.
        for i, var in enumerate(self._name_vars):
            if var.get().strip() in ("", self._default_name(self._names_mode, i)):
                var.set(self._default_name(new_mode, i))
        self._names_mode = new_mode
        self._build_color_rows()
        if self._game is not None and not self._game.in_progress:
            self._start_game(self._game.board, self._map_id)

    def _update_mode_lock(self):
        """Lock the player-count options and the names while a match is in progress."""
        locked = self._game is not None and self._game.in_progress
        for button in self._mode_buttons + self._difficulty_buttons:
            button.config(state="disabled" if locked else "normal")
        self._difficulty_box.config(
            text="Difficulty (locked during match)" if locked else "Difficulty"
        )
        for box, text in ((self._single_box, "Singleplayer"), (self._multi_box, "Multiplayer")):
            box.config(text=f"{text} (locked during match)" if locked else text)
        for entry in self._name_entries:
            entry.config(state="disabled" if locked else "normal")
        for menu in self._color_menus:
            menu.config(state="disabled" if locked else "normal")
        self._colors_frame.config(
            text="Names & colors (locked during match)" if locked else "Names & colors"
        )

    def _start_game(self, board, map_id):
        self._cancel_animation()
        mode = self._mode.get()
        count = self._participant_count(mode)
        names = [var.get().strip() for var in self._name_vars[:count]]
        try:
            game = Game(
                count,
                board=board,
                player_names=names,
                player_colors=[var.get() for var in self._color_vars[:count]],
                computer_players=[i >= self.MODES[mode][1] for i in range(count)],
                difficulty=self._selected_difficulty(),
            )
        except (SnakesAndLaddersError, ValueError) as error:
            messagebox.showerror("Cannot start game", str(error))
            return False
        self._game = game
        self._game_mode = mode
        self._map_id = map_id
        self._run_toss()
        return True

    def _enter_match(self):
        """Show the match screen for the current game (after the starting toss)."""
        game = self._game
        self._show_game_screen()
        self._show_map_id()
        self._level_label.config(text=game.difficulty.label)
        self._layout_label.config(
            text=f"{len(game.board.snakes)} snakes, {len(game.board.ladders)} ladders"
        )
        self._draw_board()
        self._draw_tokens()
        self._build_player_panel()
        self._draw_dice(None)
        self._log.delete(0, tk.END)
        self._write_log("Start match")
        self._update_status()
        self._update_mode_lock()
        self._prepare_next_turn()

    # ================================================================== starting toss
    def _run_toss(self):
        """Separate window where everyone tosses the dice; the result sets the player order.

        Each toss uses two dice; the order is by each player's latest total, highest
        first. Players sharing a total toss again until all totals differ (see
        StartToss). Closing the window cancels the match.
        """
        game = self._game
        toss = StartToss(game.players, game.dice)
        players = game.players

        dialog = tk.Toplevel(self._root, padx=16, pady=12)
        dialog.title("Who starts?")
        dialog.resizable(False, False)
        dialog.transient(self._root)
        dialog.grab_set()

        tk.Label(dialog, text="Toss two dice - highest current total starts",
                 font=("Helvetica", 13, "bold")).pack(pady=(0, 2))
        round_label = tk.Label(dialog, text="", font=("Helvetica", 11, "bold"), fg="#546e7a")
        round_label.pack()

        table = tk.LabelFrame(dialog, text="Players", padx=8, pady=4)
        table.pack(fill="x", pady=8)

        middle = tk.Frame(dialog)
        middle.pack(pady=(0, 6))
        dice_canvases = []
        for _ in range(toss.dice_count):
            canvas = tk.Canvas(middle, width=self.DICE_SIZE, height=self.DICE_SIZE,
                               highlightthickness=0)
            canvas.pack(side="left", padx=2)
            dice_canvases.append(canvas)
        status = tk.Label(middle, text="", font=("Helvetica", 12, "bold"), width=18)
        status.pack(side="left", padx=8)
        message = tk.Label(dialog, text="", fg="#546e7a", width=50, height=3, wraplength=360)
        message.pack()

        button = tk.Button(dialog, text="Roll Dice  (Space)", width=20, bg="#bbdefb",
                           font=("Helvetica", 11, "bold"))
        button.pack(pady=(6, 0))
        pending = [None]  # after() id of the computer's scheduled toss

        def fill_table():
            for widget in table.winfo_children():
                widget.destroy()
            # Rows keep the players' own order; once decided, each row shows its place.
            places = {p: i + 1 for i, p in enumerate(toss.ranking or ())}
            for row, player in enumerate(players):
                out = not toss.is_decided and player not in toss.contenders
                color = "#9e9e9e" if out else "black"
                font = ("Helvetica", 10, "bold" if player is toss.winner else "normal")
                place = f"{places[player]}{self._ordinal_suffix(places[player])}" if places else ""
                tk.Label(table, text=f"{row + 1}.", width=3, anchor="w", fg=color,
                         font=font).grid(row=row, column=0, sticky="w")
                tk.Label(table, text=place, width=4, anchor="w", fg="#2e7d32",
                         font=("Helvetica", 10, "bold")).grid(row=row, column=4, sticky="w")
                tk.Label(table, bg=Game.color_code(player.color), width=2, relief="solid",
                         bd=1).grid(row=row, column=1, padx=(0, 6), pady=2)
                tk.Label(table, text=player.name, width=15, anchor="w", fg=color,
                         font=font).grid(row=row, column=2, sticky="w")
                values = "  ".join(str(v) for v in toss.tosses(player)) or "-"
                tk.Label(table, text=values, width=12, anchor="w", fg=color,
                         font=("Consolas", 10, "bold")).grid(row=row, column=3, sticky="w")
            # Always Game.MAX_PLAYERS rows so the table keeps its height; unused rows stay empty.
            for row in range(len(players), Game.MAX_PLAYERS):
                tk.Label(table, width=2, bd=1, relief="flat").grid(
                    row=row, column=1, padx=(0, 6), pady=2)

        def next_step():
            fill_table()
            if toss.is_decided:
                round_label.config(text="Toss decided")
                winner = toss.winner
                you = winner.name.casefold() == "you"
                status.config(text="You start!" if you else f"{winner.name} starts!",
                              bg=Game.color_code(winner.color))
                button.config(text="Start Match", bg="#c8e6c9", state="normal", command=finish)
                return
            round_label.config(text=f"Round {toss.round}")
            player = toss.next_player
            status.config(text=f"Toss: {player.name}", bg=Game.color_code(player.color))
            if player.is_computer:
                button.config(state="disabled")
                pending[0] = dialog.after(self.COMPUTER_DELAY_MS, lambda: roll(by_computer=True))
            else:
                button.config(state="normal")

        def roll(by_computer=False):
            if toss.is_decided or toss.next_player.is_computer != by_computer:
                return
            pending[0] = None
            result = toss.roll()
            for value, canvas in zip(result.values, dice_canvases):
                self._draw_dice(value, canvas)
            if result.winner is not None:
                message.config(text="Every place is decided.")
            elif result.round_over:
                ties = []
                for total, group in result.ties:
                    names = [p.name for p in group]
                    ties.append(f"tie on {total}: " + ", ".join(names[:-1]) + " and " + names[-1])
                message.config(text="Toss again - " + "; ".join(ties) + ".")
            next_step()

        def finish():
            dialog.destroy()
            game.set_turn_order(toss.ranking)
            self._enter_match()

        def cancel():
            if pending[0] is not None:
                dialog.after_cancel(pending[0])
            dialog.destroy()
            self._game = None
            self._update_mode_lock()
            self._show_start_menu()

        button.config(command=roll)
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        dialog.bind("<space>", lambda _event: button.invoke())
        dialog.bind("<Return>", lambda _event: button.invoke())
        for canvas in dice_canvases:
            self._draw_dice(None, canvas)
        next_step()
        dialog.update_idletasks()
        x = self._root.winfo_rootx() + (self._root.winfo_width() - dialog.winfo_width()) // 2
        y = self._root.winfo_rooty() + (self._root.winfo_height() - dialog.winfo_height()) // 3
        dialog.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        dialog.focus_set()

    @staticmethod
    def _ordinal_suffix(number):
        return {1: "st", 2: "nd", 3: "rd"}.get(number, "th")

    # ================================================================== turns
    def roll_dice(self, by_computer=False):
        """Play one turn for the current player and animate the move."""
        if self._game is None or self._after_id is not None or self._game.is_over:
            return
        if self._game.current_player.is_computer != by_computer:
            return  # humans can't roll for the computer and vice versa
        try:
            result = self._game.play_turn()
        except GameOverError as error:
            messagebox.showinfo("Game over", str(error))
            return
        except SnakesAndLaddersError as error:
            messagebox.showerror("Error", str(error))
            return

        if len(self._game.history) == 1:
            self._save_current_map()  # the match has started: keep its map in the history
        self._draw_dice(result.roll)
        self._roll_button.config(state="disabled")
        self._update_mode_lock()

        index = self._game.players.index(result.player)
        if result.bounced:  # walk up to the last square, then back down
            size = self._game.board.size
            path = list(range(result.start + 1, size + 1)) + list(range(size - 1, result.landed - 1, -1))
        else:
            path = list(range(result.start + 1, result.landed + 1))
        if result.end != result.landed:
            path.append(result.end)
        self._animate(index, path, result)

    def _confirm(self, title, question):
        """Yes/No dialog; warns that progress is lost when a match is under way."""
        if self._game is not None and self._game.in_progress:
            question += "\nThe current match's progress will be lost."
        return messagebox.askyesno(title, question)

    def exit_game(self):
        if messagebox.askyesno("Exit", "Are you sure you want to exit?"):
            self._cancel_animation()
            self._root.destroy()

    # ================================================================== match history
    def _show_map_id(self):
        level = self._game.difficulty
        saved = self._match_history.contains(level, self._map_id)
        note = "" if saved else "  (saved on first roll)"
        self._map_label.config(text=f"Match ID: {self._map_id}{note}")
        record = self._match_history.record(level, self._map_id, self._record_kind())
        perfect = self._is_perfect(record, self._game.board, level)
        self._record_label.config(
            text=f"Record: {self._record_text(record, 'Undetermined')}",
            fg=self.GOLD if perfect else self.RECORD_COLOR,
        )

    def _record_kind(self):
        """Singleplayer and multiplayer matches keep separate records."""
        computers = self.MODES[self._game_mode][2]
        return MatchHistory.SINGLE if computers else MatchHistory.MULTI

    @staticmethod
    def _record_text(record, undetermined):
        if record is None:
            return undetermined
        text = f"{record.steps} steps"
        return f"{text} ({record.holder})" if record.holder else text

    @staticmethod
    def _is_perfect(record, board, level):
        """True when a record equals the fewest steps the board allows."""
        return record is not None and record.steps == Game.min_steps(board, level)

    def _save_current_map(self):
        try:
            self._match_history.save(self._game.difficulty, self._map_id, self._game.board)
        except MatchHistoryError as error:
            self._write_log(str(error))
            return
        self._show_map_id()

    def _save_record(self, winner):
        """Update this map's record (of the current mode's kind) after a win.

        In singleplayer the record belongs to the human player only: their win keeps it (or
        lowers it), while an AI rival's win resets it to undetermined. In multiplayer any
        player's win can set it; the first player counts as "You", the others as "Rival".
        """
        steps = sum(r.steps for r in self._game.history if r.player is winner)
        level = self._game.difficulty
        if not self._match_history.contains(level, self._map_id):
            self._save_current_map()
        try:
            kind = self._record_kind()
            if winner.is_computer:
                changed = self._match_history.clear_record(level, self._map_id, kind)
                message = f"Record for match {self._map_id} reset: an AI rival won"
            else:
                holder = ""
                if kind == MatchHistory.MULTI:
                    holder = "You" if winner is self._game.players[0] else "Rival"
                changed = self._match_history.update_record(level, self._map_id, kind, steps,
                                                            holder)
                record = self._record_text(Record(steps, holder), "")
                message = f"New record for match {self._map_id}: {record}"
        except MatchHistoryError as error:
            self._write_log(str(error))
            return
        if changed:
            self._write_log(message)
            self._show_map_id()

    def open_history(self):
        """Let the player pick a saved map of any difficulty level and play it again."""
        maps = self._match_history.all_maps()
        if not maps:
            messagebox.showinfo(
                "History matches", "No saved matches yet. Start a match to save it."
            )
            return

        dialog = tk.Toplevel(self._root)
        dialog.title("History matches")
        dialog.resizable(False, False)
        dialog.transient(self._root)
        dialog.grab_set()

        tk.Label(dialog, text="All matches, every difficulty level",
                 font=("Helvetica", 10, "bold"), padx=10, pady=6).pack(anchor="w")
        # Opened from the match screen: point out the match being played right now.
        current_id = self._map_id if self._game is not None else None
        if current_id is not None:
            tk.Label(dialog, text=f"▶ Current match: {current_id}", fg="#2e7d32",
                     font=("Helvetica", 10, "bold"), padx=10).pack(anchor="w", pady=(0, 6))

        search_row = tk.Frame(dialog, padx=10)
        search_row.pack(fill="x")
        tk.Label(search_row, text="Find ID:").pack(side="left")
        query = tk.StringVar()
        tk.Entry(search_row, textvariable=query, width=10).pack(side="left", padx=6)

        row_format = "{:<2}{:<8}{:<8}{:<21}{:<18}"
        record_width = 23
        header = row_format.format("", "ID", "Level", "Created", "Layout")
        header += f"{'Record (Singleplayer)':<{record_width}}Record (Multiplayer)"
        tk.Label(dialog, text=header,
                 font=("Consolas", 10, "bold"), padx=11, anchor="w").pack(fill="x", pady=(6, 0))

        list_frame = tk.Frame(dialog, padx=10, pady=2)
        list_frame.pack(fill="both", expand=True)
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        # Each Record column is its own listbox so a record can be colored on its own (gold
        # when it is the best possible); they scroll and select together with the main one.
        boxes = tk.Frame(list_frame, bd=1, relief="sunken")
        boxes.pack(side="left", fill="both", expand=True)
        box_style = {"height": 12, "font": ("Consolas", 10), "bd": 0, "highlightthickness": 0}

        def on_scroll(first, last_visible):
            scrollbar.set(first, last_visible)
            for box in record_boxes:
                box.yview_moveto(first)

        listbox = tk.Listbox(boxes, width=len(row_format.format(*[""] * 5)), activestyle="dotbox",
                             yscrollcommand=on_scroll, **box_style)
        listbox.pack(side="left", fill="both", expand=True)
        record_boxes = []
        for _kind in (MatchHistory.SINGLE, MatchHistory.MULTI):
            box = tk.Listbox(boxes, width=record_width, activestyle="none", exportselection=False,
                             takefocus=0, **box_style)
            box.pack(side="left", fill="y")
            record_boxes.append(box)
        scrollbar.config(command=listbox.yview)

        shown = []
        last = [None]  # last selected row, to step over the current match's row
        clicked = [False]  # the next selection change comes from the mouse

        def is_current(index):
            return shown[index].map_id == current_id

        def sync_records(*_args):
            for box in record_boxes:
                box.selection_clear(0, tk.END)
                for index in listbox.curselection():
                    box.selection_set(index)
                box.yview_moveto(listbox.yview()[0])

        def fill_list(*_args):
            text = query.get().strip().upper()
            listbox.delete(0, tk.END)
            for box in record_boxes:
                box.delete(0, tk.END)
            shown.clear()
            for saved in maps:
                if text in saved.map_id:
                    shown.append(saved)
                    layout = f"{len(saved.board.snakes)}S/{len(saved.board.ladders)}L"
                    current = saved.map_id == current_id
                    listbox.insert(tk.END, row_format.format(
                        "►" if current else "", saved.map_id, saved.difficulty.label,
                        saved.created, f"{layout:<7}(playing)" if current else layout
                    ))
                    for box, record in zip(record_boxes, (saved.single_record, saved.multi_record)):
                        box.insert(tk.END, self._record_text(record, "-"))
                    if current:
                        # The match being played cannot be chosen; it is only pointed out.
                        for box in (listbox, *record_boxes):
                            box.itemconfig(tk.END, bg="#c8e6c9", fg="#757575",
                                           selectbackground="#c8e6c9", selectforeground="#757575")
                    for box, record in zip(record_boxes, (saved.single_record, saved.multi_record)):
                        if self._is_perfect(record, saved.board, saved.difficulty):
                            box.itemconfig(tk.END, fg=self.GOLD, selectforeground=self.GOLD_SELECTED)
            # Start on the first row other than the current match.
            last[0] = next((i for i in range(len(shown)) if not is_current(i)), None)
            if last[0] is not None:
                listbox.selection_set(last[0])
                listbox.activate(last[0])
                listbox.see(last[0])
            sync_records()

        def on_select(_event):
            from_mouse, clicked[0] = clicked[0], False
            selection = listbox.curselection()
            if not selection or not is_current(selection[0]):
                last[0] = selection[0] if selection else None
                return
            # A click on it keeps the previous choice; arrow keys step past it.
            index = selection[0]
            step = 1 if last[0] is None or last[0] < index else -1
            if from_mouse or not 0 <= index + step < len(shown):
                target = last[0]
            else:
                target = index + step
            listbox.selection_clear(0, tk.END)
            if target is not None:
                listbox.selection_set(target)
                listbox.activate(target)
                listbox.see(target)
            last[0] = target

        def play(event=None):
            on_row = event is not None and event.type == tk.EventType.ButtonPress and shown
            if on_row and is_current(listbox.nearest(event.y)):
                return  # double-click on the current match
            selection = listbox.curselection()
            if not selection:
                return
            if is_current(selection[0]):
                return  # already being played
            saved = shown[selection[0]]
            if self._game is not None and self._game.in_progress and not messagebox.askyesno(
                "History matches", "A match is in progress. Abandon it and play this match?",
                parent=dialog,
            ):
                return
            dialog.destroy()
            # The match is replayed on its own level, so Settings switch to that level too.
            self._loading_saved_map = True
            try:
                self._difficulty.set(saved.difficulty.label)
            finally:
                self._loading_saved_map = False
            self._start_game(saved.board, saved.map_id)

        query.trace_add("write", fill_list)
        listbox.bind("<Double-Button-1>", play)
        listbox.bind("<Return>", play)
        listbox.bind("<<ListboxSelect>>", lambda event: (on_select(event), sync_records()))
        listbox.bind("<ButtonPress-1>", lambda _event: clicked.__setitem__(0, True), add="+")

        # Clicks and wheel turns on the Record columns act on the main list.
        def record_click(event):
            index = event.widget.nearest(event.y)
            if 0 <= index < len(shown):
                clicked[0] = True
                listbox.selection_clear(0, tk.END)
                listbox.selection_set(index)
                listbox.activate(index)
                listbox.focus_set()
                listbox.event_generate("<<ListboxSelect>>")
            return "break"

        def record_wheel(event):
            listbox.yview_scroll(-1 if event.delta > 0 else 1, "units")
            return "break"

        for box in record_boxes:
            box.bind("<ButtonPress-1>", record_click)
            box.bind("<B1-Motion>", lambda _event: "break")
            box.bind("<Double-Button-1>", lambda event: (play(event), "break")[1])
            box.bind("<MouseWheel>", record_wheel)
        fill_list()

        buttons = tk.Frame(dialog, pady=8)
        buttons.pack()
        tk.Button(buttons, text="Play this match", width=14, bg="#c8e6c9", command=play).pack(
            side="left", padx=4
        )
        tk.Button(buttons, text="Cancel", width=10, command=dialog.destroy).pack(side="left", padx=4)
        listbox.focus_set()

    # ================================================================== turn flow
    def _animate(self, index, path, result):
        if path:
            self._move_token(index, path.pop(0))
            self._after_id = self._root.after(
                self.ANIMATION_DELAY_MS, self._animate, index, path, result
            )
        else:
            self._after_id = None
            self._finish_turn(result)

    def _cancel_animation(self):
        if self._after_id is not None:
            self._root.after_cancel(self._after_id)
            self._after_id = None

    def _finish_turn(self, result):
        self._write_log(self._describe(result))
        self._refresh_player_panel()
        if result.is_winner:
            self._write_log(f"Winner: {result.player.name}")
            self._save_record(result.player)
            self._update_status()
            self._roll_button.config(state="disabled")
            self._update_mode_lock()
            messagebox.showinfo("Game over", self._winner_text(result.player))
        else:
            self._update_status()
            self._prepare_next_turn()

    def _prepare_next_turn(self):
        """Enable the Roll button for humans, or schedule the computer's roll."""
        if self._game.current_player.is_computer:
            self._roll_button.config(state="disabled")
            self._after_id = self._root.after(self.COMPUTER_DELAY_MS, self._computer_turn)
        else:
            self._roll_button.config(state="normal")

    def _computer_turn(self):
        self._after_id = None
        self.roll_dice(by_computer=True)

    @staticmethod
    def _winner_headline(player):
        return "You win!" if player.name.casefold() == "you" else f"{player.name} wins!"

    def _winner_text(self, player):
        if player.is_computer:
            return f"{self._winner_headline(player)} Better luck next time."
        return f"{self._winner_headline(player)} Congratulations!"

    def _describe(self, result):
        text = f"{result.player.name} rolled {result.roll}: "
        if result.overshoot and not result.bounced and not result.is_winner:
            return text + f"needs an exact roll, stays on {result.start}."
        if result.bounced:
            text += f"{result.start} -> {self._game.board.size}, bounces back to {result.landed}"
        else:
            text += f"{result.start} -> {result.landed}"
        if result.event == Board.SNAKE:
            text += f", snake! slides down to {result.end}"
        elif result.event == Board.LADDER:
            text += f", ladder! climbs up to {result.end}"
        return text + "."

    def _update_status(self):
        if self._game.is_over:
            player = self._game.winner
            text = self._winner_headline(player)
        else:
            player = self._game.current_player
            text = f"Turn: {player.name}"
        self._status.config(text=text, bg=Game.color_code(player.color), fg="black", padx=8)

    def _write_log(self, message):
        self._log.insert(tk.END, message)
        self._log.see(tk.END)

    # ================================================================== names & colors
    def _participant_count(self, mode):
        _text, humans, computers = self.MODES[mode]
        return humans + computers

    def _default_name(self, mode, index):
        _text, _humans, computers = self.MODES[mode]
        if computers:  # singleplayer: "You" against the AI rivals
            if index == 0:
                return "You"
            if index <= computers:
                return ComputerPlayer.names(computers)[index - 1]
        return f"Player {index + 1}"

    def _build_color_rows(self):
        for widget in self._colors_frame.winfo_children():
            widget.destroy()
        self._color_menus = []
        self._name_entries = []
        count = self._participant_count(self._mode.get())
        # Always Game.MAX_PLAYERS rows so the window keeps its size; rows of players
        # outside this mode stay empty, uncolored and disabled.
        for row in range(Game.MAX_PLAYERS):
            used = row < count
            tk.Label(self._colors_frame, text=f"{row + 1}.", width=4, anchor="w",
                     state="normal" if used else "disabled").grid(row=row, column=0)
            if used:
                entry = tk.Entry(self._colors_frame, textvariable=self._name_vars[row], width=15)
                menu = tk.OptionMenu(self._colors_frame, self._color_vars[row], *sorted(Game.COLORS))
                self._name_entries.append(entry)
                self._color_menus.append(menu)
            else:
                entry = tk.Entry(self._colors_frame, width=15, state="disabled")
                menu = tk.OptionMenu(self._colors_frame, tk.StringVar(value=""), "")
                menu.config(state="disabled")
            entry.grid(row=row, column=1, padx=(0, 6), pady=1)
            menu.config(width=7)
            menu.grid(row=row, column=2, pady=1, sticky="w")
        self._paint_color_menus()
        self._check_names()
        self._update_mode_lock()

    def _check_names(self):
        """Validate the visible names; highlight the boxes and return the names or None."""
        names = [var.get() for var in self._name_vars[:len(self._name_entries)]]
        try:
            Game.validate_names(names)
        except SnakesAndLaddersError as error:
            self._name_error.config(text=str(error))
            for entry in self._name_entries:
                entry.config(bg="#ffcdd2")
            return None
        self._name_error.config(text="")
        for entry in self._name_entries:
            entry.config(bg="white")
        return [name.strip() for name in names]

    def _on_name_changed(self):
        """Rename the running game's players as you type, as long as the names are valid."""
        if not hasattr(self, "_name_error"):
            return  # UI not built yet
        names = self._check_names()
        if names is None or self._game is None or self._game_mode != self._mode.get():
            return
        if len(names) != len(self._game.players):
            return
        try:
            self._game.set_player_names(names)
        except SnakesAndLaddersError:
            return
        self._refresh_player_panel()
        self._update_status()

    def _paint_color_menus(self):
        for menu, var in zip(self._color_menus, self._color_vars):
            code = Game.color_code(var.get())
            menu.config(bg=code, activebackground=code)

    def _on_color_changed(self, index):
        """Keep colors unique by swapping with whoever had the chosen color, then apply."""
        if self._updating_colors:
            return
        chosen = self._color_vars[index].get()
        old = self._previous_colors[index]
        self._updating_colors = True
        try:
            for other, var in enumerate(self._color_vars):
                if other != index and var.get() == chosen:
                    var.set(old)
        finally:
            self._updating_colors = False
        self._previous_colors = [var.get() for var in self._color_vars]
        self._paint_color_menus()
        self._apply_colors_to_game()

    def _apply_colors_to_game(self):
        """Recolor the running game immediately (if it uses the currently selected mode)."""
        if self._game is None or self._game_mode != self._mode.get():
            return
        count = len(self._game.players)
        try:
            self._game.set_player_colors([var.get() for var in self._color_vars[:count]])
        except SnakesAndLaddersError as error:
            messagebox.showerror("Color error", str(error))
            return
        for index, player in enumerate(self._game.players):
            self._canvas.itemconfig(self._tokens[index], fill=Game.color_code(player.color))
        self._build_player_panel()
        self._update_status()

    # ================================================================== players panel
    def _build_player_panel(self):
        for widget in self._players_frame.winfo_children():
            widget.destroy()
        self._player_labels = []
        players = self._game.turn_order  # listed in the order decided by the toss
        # Always Game.MAX_PLAYERS rows so the panel keeps its height; unused rows stay empty.
        for row in range(Game.MAX_PLAYERS):
            if row < len(players):
                swatch = {"bg": Game.color_code(players[row].color), "relief": "solid"}
            else:
                swatch = {"relief": "flat"}
            tk.Label(self._players_frame, width=2, bd=1, **swatch).grid(
                row=row, column=0, padx=(0, 6), pady=2
            )
            label = tk.Label(self._players_frame, anchor="w")
            label.grid(row=row, column=1, sticky="w")
            if row < len(players):
                self._player_labels.append(label)
        self._refresh_player_panel()

    def _refresh_player_panel(self):
        steps = {player: 0 for player in self._game.players}
        for result in self._game.history:
            steps[result.player] += result.steps
        for label, player in zip(self._player_labels, self._game.turn_order):
            count = steps[player]
            label.config(text=f"{player.name}: {count} step{'' if count == 1 else 's'}")

    # ================================================================== geometry
    def _square_bounds(self, square):
        row, col = divmod(square - 1, self.GRID)
        if row % 2 == 1:  # boustrophedon: every other row runs right-to-left
            col = self.GRID - 1 - col
        x0 = col * self.CELL
        y0 = (self.GRID - 1 - row) * self.CELL
        return x0, y0, x0 + self.CELL, y0 + self.CELL

    def _square_center(self, square):
        x0, y0, x1, y1 = self._square_bounds(square)
        return (x0 + x1) / 2, (y0 + y1) / 2

    def _token_coords(self, index, square):
        radius = self.CELL * 0.16
        if square == 0:
            x = 30 + index * 40
            y = self._board_pixels + self.START_STRIP / 2
        else:
            cx, cy = self._square_center(square)
            ox, oy = self.TOKEN_OFFSETS[index]
            x, y = cx + ox * self.CELL, cy + oy * self.CELL
        return x - radius, y - radius, x + radius, y + radius

    # ================================================================== drawing
    def _draw_board(self):
        canvas = self._canvas
        canvas.delete("all")
        board = self._game.board

        for square in range(1, board.size + 1):
            x0, y0, x1, y1 = self._square_bounds(square)
            fill = self.SQUARE_COLORS[(int(x0 // self.CELL) + int(y0 // self.CELL)) % 2]
            if square == board.size:
                fill = "#ffd54f"
            elif square == 1:
                fill = "#a5d6a7"
            canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline="#b0bec5")
            canvas.create_text(x0 + 4, y0 + 3, text=str(square), anchor="nw",
                               font=("Helvetica", 9, "bold"), fill="#455a64")

        strip_top = self._board_pixels
        canvas.create_rectangle(0, strip_top, self._board_pixels, strip_top + self.START_STRIP,
                                fill="#eceff1", outline="#b0bec5")
        canvas.create_text(self._board_pixels - 60, strip_top + self.START_STRIP / 2,
                           text="START", font=("Helvetica", 14, "bold"), fill="#78909c")

        for bottom, top in board.ladders.items():
            self._draw_ladder(bottom, top)
        for i, (head, tail) in enumerate(board.snakes.items()):
            self._draw_snake(head, tail, self.SNAKE_COLORS[i % len(self.SNAKE_COLORS)])

    def _draw_ladder(self, bottom, top):
        x0, y0 = self._square_center(bottom)
        x1, y1 = self._square_center(top)
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        px, py = -dy / length, dx / length  # unit vector perpendicular to the ladder
        half = self.CELL * 0.15

        for sign in (-1, 1):
            self._canvas.create_line(x0 + sign * px * half, y0 + sign * py * half,
                                     x1 + sign * px * half, y1 + sign * py * half,
                                     width=4, fill=self.LADDER_COLOR)
        rungs = max(2, int(length // 20))
        for i in range(1, rungs):
            t = i / rungs
            cx, cy = x0 + dx * t, y0 + dy * t
            self._canvas.create_line(cx - px * half, cy - py * half, cx + px * half, cy + py * half,
                                     width=3, fill=self.LADDER_COLOR)

    def _draw_snake(self, head, tail, color):
        hx, hy = self._square_center(head)
        tx, ty = self._square_center(tail)
        dx, dy = tx - hx, ty - hy
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        amplitude = self.CELL * 0.22
        waves = max(1, round(length / (self.CELL * 1.5)))

        points = []
        steps = 48
        for i in range(steps + 1):
            t = i / steps
            offset = amplitude * math.sin(t * waves * 2 * math.pi)
            points.extend((hx + dx * t + px * offset, hy + dy * t + py * offset))
        self._canvas.create_line(*points, smooth=True, width=9, fill=color, capstyle=tk.ROUND)

        r = self.CELL * 0.17
        self._canvas.create_oval(hx - r, hy - r, hx + r, hy + r, fill=color, outline="black")
        for sign in (-1, 1):
            ex, ey = hx - ux * r * 0.3 + px * sign * r * 0.45, hy - uy * r * 0.3 + py * sign * r * 0.45
            self._canvas.create_oval(ex - 2.5, ey - 2.5, ex + 2.5, ey + 2.5, fill="white", outline="")
        self._canvas.create_line(hx - ux * r, hy - uy * r, hx - ux * r * 1.8, hy - uy * r * 1.8,
                                 fill="red", width=2)

    def _draw_tokens(self):
        self._tokens = {}
        for index, player in enumerate(self._game.players):
            self._tokens[index] = self._canvas.create_oval(
                *self._token_coords(index, player.position),
                fill=Game.color_code(player.color), outline="black", width=2,
            )

    def _move_token(self, index, square):
        token = self._tokens[index]
        self._canvas.coords(token, *self._token_coords(index, square))
        self._canvas.tag_raise(token)

    def _draw_dice(self, value, canvas=None):
        dice = canvas or self._dice_canvas
        dice.delete("all")
        margin = 4
        side = self.DICE_SIZE - 2 * margin
        dice.create_rectangle(margin, margin, margin + side, margin + side,
                              fill="white", outline="black", width=2)
        pips = self.PIP_LAYOUT.get(value)
        if pips is None:
            dice.create_text(self.DICE_SIZE / 2, self.DICE_SIZE / 2,
                             text="?" if value is None else str(value), font=("Helvetica", 22, "bold"))
            return
        radius = side * 0.08
        for fx, fy in pips:
            x, y = margin + fx * side, margin + fy * side
            dice.create_oval(x - radius, y - radius, x + radius, y + radius, fill="black")
