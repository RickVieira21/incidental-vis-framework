import tkinter as tk
from tkinter import ttk

class ScrollableFrame(ttk.Frame):
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
    def __init__(self, root, engine):
        self.root = root
        self.engine = engine
        self.root.title("ATC Simulator")
        self.root.geometry("1450x820")
                
        self.selected_flight = None
        self.selected_flight_button = None
        self.selected_runway = None
        self.selected_runway_rect = None

        self.flight_buttons = {}
        self.runway_timer_texts = {}

        main_frame = tk.Frame(root)
        main_frame.pack(fill="both", expand=True)

        # ---------------------------
        #   TOP FRAME (RUNWAYS + FLIGHTS)
        # ---------------------------
        top_frame = tk.Frame(main_frame)
        top_frame.pack(fill="both", expand=True)

        top_frame.grid_rowconfigure(0, weight=1)
        top_frame.grid_columnconfigure(0, weight=3)  # runways mais largo
        top_frame.grid_columnconfigure(1, weight=2)  # flight list mais estreita

        # LEFT: RUNWAYS
        self.runway_frame = tk.Frame(top_frame, bg="#e6e6e6")
        self.runway_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        tk.Label(self.runway_frame, text="Runways", font=("Arial", 18, "bold")).pack(pady=5)

        self.canvas = tk.Canvas(self.runway_frame, bg="white")
        self.canvas.pack(fill="both", expand=True)

        self.draw_runways()

        # RIGHT: FLIGHT LIST 
        flight_frame = tk.Frame(top_frame)
        flight_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        tk.Label(flight_frame, text="Flight Queue", font=("Arial", 16, "bold")).pack(pady=5)

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

        # Frame branco fixo
        content_frame = tk.Frame(console_frame, bg="white")
        content_frame.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        # Canvas para permitir scroll interno
        canvas = tk.Canvas(content_frame, bg="white", highlightthickness=0)
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

    # --------------------------- RUNWAYS

    def draw_runways(self):
        lane_height = 130
        spacing = 35
        y = 20

        self.runways = {}

        for name in ["A", "B", "C"]:
            rect = self.canvas.create_rectangle(
                60, y, 750, y + lane_height,
                fill="#b3ffb3", outline="black", width=2
            )

            self.canvas.create_text(
                80, y + lane_height/2,
                text=f"Runway {name}",
                anchor="w",
                font=("Arial", 16, "bold")
            )

            text_id = self.canvas.create_text(
            650, y + lane_height/2,
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
        if not self.selected_flight_obj:
            self.add_log("No flight selected.")
            return

        runway = self.engine.get_runway(runway_name)

        if not runway.available:
            self.add_log(f"Runway {runway_name} is already occupied.")
            return

        # remover highlight anterior
        if self.selected_runway_rect:
            prev = self.selected_runway
            prev_runway = self.engine.get_runway(prev)
            if prev_runway.available:
                self.canvas.itemconfig(self.selected_runway_rect, fill="#b3ffb3")

        # novo highlight
        rect = self.runways[runway_name]
        self.canvas.itemconfig(rect, fill="#99ccff")

        self.selected_runway = runway_name
        self.selected_runway_rect = rect

        self.add_log(
            f"Do you pretend to allocate {self.selected_flight_obj.callsign} "
            f"to runway {runway_name}? Press Authorize to confirm."
        )



    def update_runway(self, runway):
        rect = self.runways[runway.name]
        text_id = self.runway_timer_texts[runway.name]

        if runway.available:
            self.canvas.itemconfig(rect, fill="#b3ffb3")
            self.canvas.itemconfig(text_id, text="")
        else:
            self.canvas.itemconfig(rect, fill="red")
            self.canvas.itemconfig(
                text_id,
                text=f"Ocupada: {runway.remaining_time}s",
                fill="white"
            )


    # --------------------------- FLIGHTS

    def add_flight(self, flight):
        self.add_flight_button(flight)


    def add_flight_button(self, flight):

        # Base
        text = f"{flight.callsign} - ETA {flight.eta}s"

        # Constraint (mostrar runway obrigatória)
        if flight.required_runway is not None:
            text += f" | Runway {flight.required_runway}"

        # Indicadores dinâmicos (sem mexer na cor base)
        if flight.is_priority:
            text = "⚡ " + text

        if flight.is_delayed:
            text = "⏳ " + text

        bg_color = self.get_flight_base_color(flight)

        btn = tk.Button(
            self.scroll.scrollable_frame,
            text=text,
            font=("Arial", 14),
            bg=bg_color,
            width=55,
            height=2
        )

        btn.config(command=lambda: self.select_flight(btn, flight))
        btn.pack(fill="x", pady=5)

        self.flight_buttons[flight] = btn




    def get_flight_base_color(self, flight):

        # prioridade tem precedência máxima
        if getattr(flight, "is_priority", False):
            return "#fff3b0"   # amarelo claro

        # atraso
        if getattr(flight, "is_delayed", False):
            return "#d9d9d9"   # cinza

        # constraint
        if flight.required_runway is not None:
            return "#ffe6e6"   # vermelho claro

        # normal
        return "#e6f0ff"       # azul claro


    def select_flight(self, button, flight):

        # restaurar botão anterior (se ainda existir)
        if (
            self.selected_flight_button
            and self.selected_flight_button.winfo_exists()
            and self.selected_flight_obj
        ):
            prev_color = self.get_flight_base_color(self.selected_flight_obj)
            self.selected_flight_button.config(bg=prev_color)

        # atualizar seleção
        self.selected_flight_button = button
        self.selected_flight_obj = flight
        self.selected_flight = flight.callsign

        # highlight azul mais forte para seleção
        if button.winfo_exists():
            button.config(bg="#99ccff")

        self.add_log(f"Selected flight: {flight.callsign}")

    
    def update_flight(self, flight):
        btn = self.flight_buttons.get(flight)

        if not btn or not btn.winfo_exists():
            return

        base_text = f"{flight.callsign} - T-{flight.eta}s"

        if flight.required_runway is not None:
            text = f"{base_text}     Runway {flight.required_runway}"
        else:
            text = base_text

        btn.config(text=text)


    def remove_flight(self, flight):
        btn = self.flight_buttons.pop(flight, None)
        if btn:
            btn.destroy()
            #self.add_log(f"Flight {flight.callsign} expired.")

    
    def refresh_flight_list(self):

        for widget in self.scroll.scrollable_frame.winfo_children():
            widget.destroy()

        self.flight_buttons.clear()

        for flight in self.engine.flights:
            self.add_flight_button(flight)

    # -----------------------------------


    def authorize(self):

        if not self.selected_flight or not self.selected_runway:
            self.add_log("Select a flight and a runway first.")
            return

        if self.selected_flight_obj not in self.engine.flights:
            self.add_log("Selected flight is no longer available.")
            self.selected_flight = None
            self.selected_flight_obj = None
            self.selected_flight_button = None
            return

        runway = self.engine.get_runway(self.selected_runway)
        flight = self.selected_flight_obj

        result = self.engine.assign_flight_to_runway(flight, runway)

        if result == "CONSTRAINT_VIOLATION":
            self.add_log(
                f"Constraint violation: {flight.callsign} "
                f"must use Runway {flight.required_runway}"
            )
            return

        if result is False:
            self.add_log(f"Runway {runway.name} is already occupied.")
            return

        # sucesso
        if flight in self.engine.flights:
            self.engine.flights.remove(flight)

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


    
    def add_system_message(self, message_obj):
        # Guardar no engine
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


    def acknowledge_message(self, message_obj, var, label):
        if not var.get():
            return

        message_obj.acknowledge()

        label.config(
            fg="green",
            font=("Arial", 13)
        )

        print("Reaction time:", message_obj.reaction_time)



class StartMenu:
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

    def start_experiment(self):
        participant_id = self.participant_var.get()
        self.frame.destroy()
        self.on_start(participant_id)



