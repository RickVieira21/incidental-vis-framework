"""
atc_ui.py

Defines the Tkinter-based graphical interface for the ATC simulation
task: ATCApp (the main in-trial interface showing runways, the flight
queue, the console log, and system messages) and StartMenu (the
initial screen where the experimenter selects a participant ID and
starts either the real experiment or a practice run).

This is the only file in the `ui` folder and is what participants
directly interact with while completing each trial.
"""

import tkinter as tk
import time
from tkinter import ttk


class ScrollableFrame(ttk.Frame):
    """
    A reusable Tkinter frame that adds vertical scrolling to its
    contents, used to hold the flight queue (which can grow beyond
    the visible area as more flights spawn).

    Usage: place widgets inside `self.scrollable_frame` (not directly
    inside the ScrollableFrame itself) — that inner frame is the one
    that actually scrolls within the canvas.
    """

    def __init__(self, container):

        super().__init__(container)

        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")


class ATCApp:
    """
    Main task interface: displays the 3 runways, the scrollable flight
    queue, a console log of events, and pending system messages with
    acknowledgement checkboxes. Also owns the AUTHORIZE button used to
    commit a flight-to-runway assignment.

    This class acts as the "ui" object referenced throughout the
    engine/scheduler/session modules (e.g. `self.ui.update_flight(...)`
    calls made by EventScheduler), so its public methods form the
    contract those other modules rely on.

    Layout overview:
        - Top-left: Runways canvas (3 horizontal lanes: A, B, C).
        - Top-right: Scrollable flight queue (one button per flight).
        - Bottom-left: Console (scrollable log + acknowledgeable
          system messages).
        - Bottom-right: AUTHORIZE button, used to confirm a
          flight-runway assignment after selecting both.

    Attributes:
        root: The Tkinter root window.
        engine (SimulationEngine): The engine whose state this UI
            reflects and whose actions (assign_flight_to_runway,
            get_runway) it triggers.
        selected_flight (str or None): Callsign of the currently
            selected flight (for display/logging convenience;
            `selected_flight_obj` is the authoritative reference).
        selected_flight_button: The Tkinter Button widget corresponding
            to the currently selected flight, so its highlight color
            can be reset when the selection changes.
        selected_runway (str or None): Name of the currently selected
            runway.
        selected_runway_rect: The Canvas rectangle item ID
            corresponding to the currently selected runway.
        selected_flight_obj (Flight or None): The actual Flight object
            currently selected, used when authorizing an assignment.
        flight_buttons (dict[Flight, tk.Button]): Maps each active
            Flight to its corresponding button widget in the queue.
        runway_timer_texts (dict[str, int]): Maps each runway name to
            the Canvas text item ID showing its remaining occupied
            time.
        system_message_widgets (dict[SystemMessage, dict]): Maps each
            pending SystemMessage to its associated row/label widgets,
            so they can be updated or removed.
        runways (dict[str, int]): Maps each runway name to its Canvas
            rectangle item ID.
    """

    def __init__(self, root, engine):
        self.root = root
        self.engine = engine
        self.root.title("ATC Simulator")

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        width = int(screen_width * 0.75)
        height = int(screen_height * 0.93)

        self.root.geometry(f"{width}x{height}+0+0")
        self.root.resizable(False, False)
                
        self.selected_flight = None
        self.selected_flight_button = None
        self.selected_runway = None
        self.selected_runway_rect = None
        self.selected_flight_obj = None

        self.flight_buttons = {}
        self.runway_timer_texts = {}
        self.system_message_widgets = {}
        self.update_message_timers()
        self.runways = {}
        self.runway_timer_texts = {}

        main_frame = tk.Frame(root)
        main_frame.pack(fill="both", expand=True)

        # ---------------------------
        #   TOP FRAME (RUNWAYS + FLIGHTS)
        # ---------------------------
        top_frame = tk.Frame(main_frame)
        top_frame.pack(fill="both", expand=True)

        top_frame.grid_rowconfigure(0, weight=1)
        top_frame.grid_columnconfigure(0, weight=3)  
        top_frame.grid_columnconfigure(1, weight=2)  

        # LEFT: RUNWAYS
        self.runway_frame = tk.Frame(top_frame, bg="#e6e6e6")
        self.runway_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        tk.Label(
            self.runway_frame,
            text="Runways",
            font=("Arial", 17, "bold"),
            bg="#e6e6e6"
        ).pack(pady=5)

        self.canvas = tk.Canvas(
            self.runway_frame,
            bg=self.runway_frame.cget("bg"),
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(fill="both", expand=True)

        self.draw_runways()

        # RIGHT: FLIGHT LIST 
        flight_frame = tk.Frame(top_frame)
        flight_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        tk.Label(
            flight_frame,
            text="Flight Queue",
            font=("Arial", 16, "bold")
        ).pack(pady=5, padx=(0, 42))

        self.scroll = ScrollableFrame(flight_frame)
        self.scroll.pack(fill="both", expand=True)

        # ---------------------------
        #   BOTTOM SECTION
        # ---------------------------
        bottom_frame = tk.Frame(main_frame)
        bottom_frame.pack(fill="x", pady=10)

        # CONSOLE (left)
        console_frame = tk.Frame(bottom_frame, bg="#d9d9d9", height=380)
        console_frame.pack(side="left", fill="x", expand=True)
        console_frame.pack_propagate(False)

        tk.Label(
            console_frame,
            text="Console",
            font=("Arial", 16, "bold"),
            bg="#d9d9d9"
        ).pack(anchor="w", padx=10, pady=5)


        content_frame = tk.Frame(console_frame, bg="white")
        content_frame.pack(fill="both", expand=True, padx=10, pady=(0, 5))


        canvas = tk.Canvas(content_frame, bg="white", highlightthickness=0)
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=canvas.yview)

        scrollable_area = tk.Frame(canvas, bg="white")

        scrollable_area.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_area, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.message_frame = scrollable_area

        # AUTHORIZE button (right)
        auth_frame = tk.Frame(bottom_frame)
        auth_frame.pack(side="right", padx=15)

        authorize_btn = tk.Button(
            auth_frame,
            text="AUTHORIZE",
            font=("Arial", 18, "bold"),
            width=10,
            height=3,
            bg="#4CAF50",
            fg="white",
            command=self.authorize
        )
        authorize_btn.pack()



    def draw_runways(self):
        """
        Draw (or redraw) the 3 runway lanes on the canvas, centered
        horizontally, stacked vertically with spacing.

        If the canvas hasn't been rendered yet (width still reads as
        1px, a common Tkinter timing quirk before the first paint),
        this reschedules itself 50ms later instead of drawing with
        incorrect dimensions.

        Rebuilds `self.runways` (name -> rectangle ID) and
        `self.runway_timer_texts` (name -> text ID) from scratch each
        time it's called, and (re-)binds a left-click handler on each
        runway rectangle to `select_runway`.
        """
        self.canvas.delete("all") 

        canvas_width = self.canvas.winfo_width()

        if canvas_width == 1: 
            self.canvas.after(50, self.draw_runways)
            return

        lane_width = 700
        lane_height = 130
        spacing = 35

        x1 = (canvas_width - lane_width) // 2
        x2 = x1 + lane_width

        y = 20

        self.runways = {}

        for name in ["A", "B", "C"]:
            rect = self.canvas.create_rectangle(
                x1, y, x2, y + lane_height,
                fill="#b3ffb3", outline="black", width=2
            )

            self.canvas.create_text(
                x1 + 20, y + lane_height / 2,
                text=f"Runway {name}",
                anchor="w",
                font=("Arial", 16, "bold")
            )

            text_id = self.canvas.create_text(
                x2 - 20, y + lane_height / 2,
                text="",
                anchor="e",
                font=("Arial", 14, "bold"),
                fill="red"
            )

            self.runway_timer_texts[name] = text_id

            self.canvas.tag_bind(rect, "<Button-1>",
                lambda e, r=name: self.select_runway(r))

            self.runways[name] = rect
            y += lane_height + spacing

    def select_runway(self, runway_name):
        """
        Handle a click on a runway lane: select it (highlighting it
        blue) if it's available, or show an error popup if it's
        already occupied.

        If a flight is already selected, prompts the participant (via
        the console log) to press AUTHORIZE to confirm the pairing.

        Args:
            runway_name (str): Name of the clicked runway ("A"/"B"/"C").
        """
        runway = self.engine.get_runway(runway_name)

        if not runway.available:
            msg = f"Runway {runway.name} is already occupied."
            self.show_error_popup(msg)
            self.add_log(f"Runway {runway_name} is already occupied.")
            return

  
        if self.selected_runway_rect:
            prev_runway = self.engine.get_runway(self.selected_runway)
            if prev_runway.available:
                self.canvas.itemconfig(self.selected_runway_rect, fill="#b3ffb3")


        rect = self.runways[runway_name]
        self.canvas.itemconfig(rect, fill="#99ccff")

        self.selected_runway = runway_name
        self.selected_runway_rect = rect

        if self.selected_flight_obj:
            self.add_log(
                f"Allocate {self.selected_flight_obj.callsign} to runway {runway_name}? Press AUTHORIZE."
            )

    def update_runway(self, runway):
        """
        Refresh the visual state of a single runway lane: its fill
        color (green=available, blue=selected, red=occupied) and its
        remaining-occupied-time text.

        Called once per second for every runway by
        EventScheduler.schedule_runway_update.

        Args:
            runway (Runway): The runway whose display should be
                refreshed.
        """
        if not hasattr(self, "runways") or runway.name not in self.runways:
            return
        rect = self.runways[runway.name]
        text_id = self.runway_timer_texts[runway.name]


        if runway.name == self.selected_runway:
            self.canvas.itemconfig(rect, fill="#99ccff")
        else:
            if runway.available:
                self.canvas.itemconfig(rect, fill="#b3ffb3")
            else:
                self.canvas.itemconfig(rect, fill="red")

        if runway.available:
            self.canvas.itemconfig(text_id, text="")
        else:
            self.canvas.itemconfig(
                text_id,
                text=f"Occupied: {runway.remaining_time}s",
                fill="white"
            )



    def add_flight(self, flight):
        """
        Register a newly generated flight in the UI by creating its
        queue button.

        Args:
            flight (Flight): The newly generated flight to display.
        """
        self.add_flight_button(flight)

    def add_flight_button(self, flight):
        """
        Create and pack a new button in the flight queue representing
        `flight`, showing its ETA, callsign, and (if applicable) its
        required runway constraint. Background color encodes urgency/
        status (see `get_flight_base_color`).

        The button's click handler selects this flight
        (`select_flight`).

        Args:
            flight (Flight): The flight to create a button for.
        """
        offset = 43

        eta_part = f"ETA {flight.eta}s"
        callsign_part = f"{flight.callsign}"
        runway_part = f"Runway {flight.required_runway}" if flight.required_runway else ""

        text = f"{' ' * offset}{eta_part} - {callsign_part} {runway_part}"

        bg_color = self.get_flight_base_color(flight)

        btn = tk.Button(
            self.scroll.scrollable_frame,
            text=text,
            font=("Arial", 14),
            bg=bg_color,
            width=55,
            height=2,
            anchor="w"
        )

        btn.config(command=lambda: self.select_flight(btn, flight))
        btn.pack(fill="x", pady=5)

        self.flight_buttons[flight] = btn

    def get_flight_base_color(self, flight):
        """
        Determine the background color for a flight's queue button
        based on its current status, in priority order:

            1. ETA <= 5s: strong red (imminent timeout).
            2. Priority flight: light yellow.
            3. Delayed flight: gray.
            4. Constrained flight (has a required runway): light blue.
            5. Otherwise (normal flight): light blue.

        Args:
            flight (Flight): The flight to determine a color for.

        Returns:
            str: A Tkinter-compatible color string (hex).
        """
        #<5 sec
        if flight.eta <= 5:
            return "#ff4d4d"  
        
        # priority
        if getattr(flight, "is_priority", False):
            return "#fff3b0"  

        # delay
        if getattr(flight, "is_delayed", False):
            return "#d9d9d9"   
        
        # constraint
        if flight.required_runway is not None:
            return "#e6f0ff"    

        # normal
        return "#e6f0ff"      
    

    def select_flight(self, button, flight):
        """
        Handle a click on a flight's queue button: select it (visually
        highlighting it) and restore the previous selection's normal
        color.

        Args:
            button (tk.Button): The button that was clicked.
            flight (Flight): The flight it represents.
        """
        if (
            self.selected_flight_button
            and self.selected_flight_button.winfo_exists()
            and self.selected_flight_obj
        ):
            prev_color = self.get_flight_base_color(self.selected_flight_obj)
            self.selected_flight_button.config(bg=prev_color)

        self.selected_flight_button = button
        self.selected_flight_obj = flight
        self.selected_flight = flight.callsign

        if button.winfo_exists():
            button.config(bg="#99ccff")


    def update_flight(self, flight):
        """
        Refresh a flight's queue button text (ETA/callsign/runway
        constraint) and background color to reflect its current state.

        Called once per second for every active flight by
        EventScheduler.schedule_flight_update. No-op if the flight's
        button no longer exists (e.g. it was just removed).

        Args:
            flight (Flight): The flight whose button should be
                refreshed.
        """
        btn = self.flight_buttons.get(flight)

        if not btn or not btn.winfo_exists():
            return

        # -------- TEXT --------

        offset = 43

        eta_part = f"ETA {flight.eta}s"
        callsign_part = f"{flight.callsign}"
        runway_part = f"Runway {flight.required_runway}" if flight.required_runway else ""

        text = f"{' ' * offset}{eta_part} - {callsign_part} {runway_part}"

        # -------- COLOR --------

        if flight == self.selected_flight_obj:
            bg_color = "#99ccff"  
        else:
            bg_color = self.get_flight_base_color(flight)

        btn.config(text=text, bg=bg_color)

    def remove_flight(self, flight):
        """
        Remove a flight's button from the queue (e.g. because it
        expired or was successfully assigned).

        Args:
            flight (Flight): The flight to remove from display.
        """
        btn = self.flight_buttons.pop(flight, None)
        if btn:
            btn.destroy()
            #self.add_log(f"Flight {flight.callsign} expired.")

    def refresh_flight_list(self):
        """
        Fully rebuild the flight queue from the engine's current
        `flights` list: destroys all existing buttons and recreates
        one per active flight, then restores the visual highlight on
        the currently selected flight (if it's still active).

        Called after a successful `authorize()` to reflect the removal
        of the just-assigned flight.
        """
        for widget in self.scroll.scrollable_frame.winfo_children():
            widget.destroy()

        self.flight_buttons.clear()

        for flight in self.engine.flights:
            self.add_flight_button(flight)

        if self.selected_flight_obj in self.flight_buttons:
            btn = self.flight_buttons[self.selected_flight_obj]
            btn.config(bg="#99ccff")
            self.selected_flight_button = btn

    # -----------------------------------

    def authorize(self):
        """
        Commit the currently selected flight-runway pairing: the main
        action triggered by the AUTHORIZE button.

        Sequence:
            1. If either a flight or a runway isn't selected, show an
               error popup and abort.
            2. If the selected flight is no longer active (e.g. it
               expired in the meantime), show an error popup, clear
               the stale selection, and abort.
            3. Attempt the assignment via
               `engine.assign_flight_to_runway`.
            4. If it's a constraint violation, show an error popup and
               abort (selection is preserved, so the participant can
               try a different runway).
            5. If the runway was already occupied (`False`), abort
               silently (no popup).
            6. On success: remove the flight from the engine's active
               list, log a "FLIGHT_DT_<decision_time>_<callsign>"
               event (decision time = seconds since the flight
               spawned), log a confirmation message to the console,
               refresh the flight queue display, and clear the current
               selections.
        """
        if not self.selected_flight or not self.selected_runway:
            #self.add_log("Select a flight and a runway first.")
            msg = f"Select a flight and a runway first."
            self.show_error_popup(msg)
            return

        if self.selected_flight_obj not in self.engine.flights:
            #self.add_log("Selected flight is no longer available.")
            msg = f"Selected flight is no longer available."
            self.show_error_popup(msg)
            self.selected_flight = None
            self.selected_flight_obj = None
            self.selected_flight_button = None
            return

        runway = self.engine.get_runway(self.selected_runway)
        flight = self.selected_flight_obj
        decision_time = time.time() - flight.spawn_time

        result = self.engine.assign_flight_to_runway(flight, runway)

        if result == "CONSTRAINT_VIOLATION":
            msg = f"Constraint violation: {flight.callsign} "f"must use Runway {flight.required_runway}"
            self.show_error_popup(msg)
            #self.add_log(
            #    f"Constraint violation: {flight.callsign} "
            #    f"must use Runway {flight.required_runway}"
            #)
            return

        if result is False:
            return

        if flight in self.engine.flights:
            self.engine.flights.remove(flight)
            self.engine.session.log_event(f"FLIGHT_DT_{decision_time:.3f}_{flight.callsign}")

        self.add_log(
            f"Flight {flight.callsign} authorized to runway {runway.name}."
        )

        self.refresh_flight_list()

        self.selected_runway_rect = None
        self.selected_runway = None
        self.selected_flight = None
        self.selected_flight_button = None
        self.selected_flight_obj = None

    def add_log(self, msg):
        """
        Append a plain text line to the console log area.

        Args:
            msg (str): The text to display.
        """
        row = tk.Frame(self.message_frame, bg="white")
        row.pack(fill="x", pady=1)

        label = tk.Label(
            row,
            text=msg,
            anchor="w",
            bg="white",
            font=("Arial", 13)
        )
        label.pack(side="left", fill="x")

    #POPUP

    def show_error_popup(self, message):
        """
        Show a brief, centered, red, borderless popup window with an
        error/warning message, which closes itself automatically after
        2 seconds.

        Used for validation feedback (missing selection, occupied
        runway, constraint violation, stale selection) that the
        participant should notice immediately, in addition to (or
        instead of) the console log.

        Args:
            message (str): The text to display in the popup.
        """
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)  
        popup.attributes("-topmost", True)

        width = 400
        height = 120

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)

        popup.geometry(f"{width}x{height}+{x}+{y}")
        popup.configure(bg="#ff4d4d")  

        label = tk.Label(
            popup,
            text=message,
            font=("Arial", 14, "bold"),
            bg="#ff4d4d",
            fg="white",
            wraplength=350,
            justify="center"
        )
        label.pack(expand=True)
        self.root.after(2000, popup.destroy)


    def add_system_message(self, message_obj):
        """
        Register a newly generated SystemMessage in the engine's list
        and display it in the console with a checkbox the participant
        can tick to acknowledge it.

        Args:
            message_obj (SystemMessage): The message to display.
        """
        self.engine.system_messages.append(message_obj)

        row = tk.Frame(self.message_frame, bg="white")
        row.pack(fill="x", pady=1)

        var = tk.BooleanVar(value=False)

        checkbox = tk.Checkbutton(
            row,
            variable=var,
            bg="white",
            command=lambda: self.acknowledge_message(message_obj, var, label)
        )
        checkbox.pack(side="left")

        label = tk.Label(
            row,
            text=f"[SYSTEM] {message_obj.text}",
            anchor="w",
            bg="white",
            font=("Arial", 13, "bold")
        )
        label.pack(side="left", fill="x")

        self.system_message_widgets[message_obj] = {
            "row": row,
            "label": label
        }

    def update_message_timers(self):
        """
        Refresh the displayed countdown ("(<n>s)") on every
        non-expired pending system message, then reschedule itself to
        run again in 1 second.

        Called once at __init__ time to kick off this independent
        self-rescheduling loop (separate from EventScheduler's own
        ticking, though both read/write related SystemMessage state).
        """
        for msg, widgets in list(self.system_message_widgets.items()):

            if msg.expired:
                continue

            label = widgets["label"]

            if not label.winfo_exists():
                continue

            remaining = int(msg.timeout - (time.time() - msg.created_at))
            remaining = max(0, remaining)

            label.config(
                text=f"[SYSTEM] {msg.text} ({remaining}s)"
            )

        self.root.after(1000, self.update_message_timers)

    def remove_system_message(self, message_obj):
        """
        Remove a system message's row from the console (e.g. because
        it expired), destroying its widgets.

        Args:
            message_obj (SystemMessage): The message to remove.
        """
        widget_dict = self.system_message_widgets.pop(message_obj, None)

        if widget_dict:
            row = widget_dict.get("row")

            if row and row.winfo_exists():
                row.destroy()

    def acknowledge_message(self, message_obj, var, label):
        """
        Handle the participant ticking a system message's
        acknowledgement checkbox: mark it acknowledged, restyle its
        label to indicate completion, and log its reaction time.

        No-op if the checkbox was unticked (var.get() is False) rather
        than ticked — this only handles the ticking action, not
        un-ticking.

        Args:
            message_obj (SystemMessage): The message being
                acknowledged.
            var (tk.BooleanVar): The checkbox's bound variable.
            label (tk.Label): The message's text label, restyled to
                green/non-bold once acknowledged.
        """
        if not var.get():
            return

        message_obj.acknowledge()

        label.config(
            fg="green",
            font=("Arial", 13)
        )

        rt = message_obj.reaction_time
        print("Reaction time:", message_obj.reaction_time)
        self.engine.session.log_event(f"MESSAGE_RT_{rt:.3f}")

    # -----------------------------------


class StartMenu:
    """
    The initial screen shown when the application launches (or when
    returning from a session via Escape): lets the experimenter pick a
    participant ID (1-30) and choose to start the real experiment or a
    practice run.

    Attributes:
        root: The Tkinter root window.
        on_start: Callback invoked with `(participant_id)` or
            `(participant_id, practice=True)` when the corresponding
            button is pressed — typically wired up to construct a new
            ExperimentalSession.
        frame (tk.Frame): The container holding all of this menu's
            widgets, destroyed when transitioning away from the menu.
        participant_var (tk.IntVar): Bound to the participant ID
            spinbox, defaulting to 1.
        spinbox (tk.Spinbox): Lets the experimenter pick a participant
            ID between 1 and 30 (matching the range of precomputed
            Latin square entries in ExperimentalSession).
    """

    def __init__(self, root, on_start_callback):
        self.root = root
        self.on_start = on_start_callback

        self.frame = tk.Frame(root, bg="#e6e6e6")
        self.frame.pack(fill="both", expand=True)

        tk.Label(
            self.frame,
            text="ATC Cognitive Load Experiment",
            font=("Arial", 22, "bold"),
            bg="#e6e6e6"
        ).pack(pady=40)

        tk.Label(
            self.frame,
            text="Select Participant ID:",
            font=("Arial", 14),
            bg="#e6e6e6"
        ).pack(pady=10)

        self.participant_var = tk.IntVar(value=1)

        self.spinbox = tk.Spinbox(
            self.frame,
            from_=1,
            to=30,
            textvariable=self.participant_var,
            font=("Arial", 14),
            width=5
        )
        self.spinbox.pack(pady=10)

        tk.Button(
            self.frame,
            text="START",
            font=("Arial", 16, "bold"),
            width=12,
            height=2,
            command=self.start_experiment
        ).pack(pady=40)


        tk.Button(
            self.frame,
            text="PRACTICE",
            font=("Arial", 14),
            width=12,
            height=2,
            bg="#cccccc",
            command=self.start_practice
        ).pack(pady=10)

    def start_experiment(self):
        """
        Handle the START button: read the chosen participant ID,
        tear down the menu, and invoke `on_start(participant_id)` to
        begin the real experiment.
        """
        participant_id = self.participant_var.get()
        self.frame.destroy()
        self.on_start(participant_id)

    def start_practice(self):
        """
        Handle the PRACTICE button: read the chosen participant ID,
        tear down the menu, and invoke
        `on_start(participant_id, practice=True)` to begin a looping
        practice run instead of the real experiment.
        """
        participant_id = self.participant_var.get()
        self.frame.destroy()
        self.on_start(participant_id, practice=True)