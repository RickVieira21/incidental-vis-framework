import tkinter as tk
import time
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
        #self.root.geometry("1450x820") #FIXO
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # metade do ecrã (lado esquerdo)
        width = int(screen_width * 0.75)
        height = int(screen_height * 0.93)

        # posição: x=0 (esquerda), y=0 (topo)
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

        # Frame branco fixo
        content_frame = tk.Frame(console_frame, bg="white")
        content_frame.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        # Canvas para permitir scroll interno
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

    # --------------------------- RUNWAYS

    def draw_runways(self):
        self.canvas.delete("all")  # limpa antes de redesenhar

        canvas_width = self.canvas.winfo_width()

        if canvas_width == 1:  # ainda não renderizado
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

        runway = self.engine.get_runway(runway_name)

        if not runway.available:
            self.add_log(f"Runway {runway_name} is already occupied.")
            return

        # remover highlight anterior
        if self.selected_runway_rect:
            prev_runway = self.engine.get_runway(self.selected_runway)
            if prev_runway.available:
                self.canvas.itemconfig(self.selected_runway_rect, fill="#b3ffb3")

        # novo highlight
        rect = self.runways[runway_name]
        self.canvas.itemconfig(rect, fill="#99ccff")

        self.selected_runway = runway_name
        self.selected_runway_rect = rect

        if self.selected_flight_obj:
            self.add_log(
                f"Allocate {self.selected_flight_obj.callsign} to runway {runway_name}? Press AUTHORIZE."
            )



    def update_runway(self, runway):
      
        if not hasattr(self, "runways") or runway.name not in self.runways:
            return
        rect = self.runways[runway.name]
        text_id = self.runway_timer_texts[runway.name]

        # se for a runway selecionada, manter highlight
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


    # --------------------------- FLIGHTS

    def add_flight(self, flight):
        self.add_flight_button(flight)


    def add_flight_button(self, flight):

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
        
        #<5 sec
        if flight.eta <= 5:
            return "#ff4d4d"  # vermelho forte
        
        # priority
        if getattr(flight, "is_priority", False):
            return "#fff3b0"   # amarelo claro

        # delay
        if getattr(flight, "is_delayed", False):
            return "#d9d9d9"   # cinza
        
        # constraint
        if flight.required_runway is not None:
            return "#e6f0ff"    # vermelho claro #ffe6e6

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

        #self.add_log(f"Selected flight: {flight.callsign}")

    
    def update_flight(self, flight):

        btn = self.flight_buttons.get(flight)

        if not btn or not btn.winfo_exists():
            return

        # -------- TEXTO --------

        offset = 43

        eta_part = f"ETA {flight.eta}s"
        callsign_part = f"{flight.callsign}"
        runway_part = f"Runway {flight.required_runway}" if flight.required_runway else ""

        text = f"{' ' * offset}{eta_part} - {callsign_part} {runway_part}"

        # -------- COR --------

        if flight == self.selected_flight_obj:
            bg_color = "#99ccff"  # manter highlight da seleção
        else:
            bg_color = self.get_flight_base_color(flight)

        btn.config(text=text, bg=bg_color)


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

        # restaurar seleção visual
        if self.selected_flight_obj in self.flight_buttons:
            btn = self.flight_buttons[self.selected_flight_obj]
            btn.config(bg="#99ccff")
            self.selected_flight_button = btn

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
        decision_time = time.time() - flight.spawn_time

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


    #System Messages

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

        self.system_message_widgets[message_obj] = {
            "row": row,
            "label": label
        }

    
    def update_message_timers(self):

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
        widget_dict = self.system_message_widgets.pop(message_obj, None)

        if widget_dict:
            row = widget_dict.get("row")

            if row and row.winfo_exists():
                row.destroy()


    def acknowledge_message(self, message_obj, var, label):
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
        participant_id = self.participant_var.get()
        self.frame.destroy()
        self.on_start(participant_id)

    def start_practice(self):
        participant_id = self.participant_var.get()
        self.frame.destroy()
        self.on_start(participant_id, practice=True)


