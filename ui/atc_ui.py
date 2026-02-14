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
        bottom_frame.pack(fill="x", pady=5)

        # CONSOLE (left)
        console_frame = tk.Frame(bottom_frame, bg="#d9d9d9", height=130)
        console_frame.pack(side="left", fill="x", expand=True)

        tk.Label(console_frame, text="Console", font=("Arial", 14, "bold"), bg="#d9d9d9")\
            .pack(anchor="w", padx=10, pady=5)

        self.log = tk.Text(console_frame, height=6, state="disabled")
        self.log.pack(fill="x", padx=10, pady=(0, 5))

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
            self.add_log(f"Pista {runway_name} está ocupada.")
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
            f"Pretende atribuir o voo {self.selected_flight_obj.callsign} "
            f"à pista {runway_name}? Carregar Authorize para confirmar."
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
        text = f"{flight.callsign} - ETA {flight.eta}s"
        self.add_flight_button(flight, text)


    def add_flight_button(self, flight, text):
        btn = tk.Button(
            self.scroll.scrollable_frame,
            text=text,
            font=("Arial", 14),
            bg="#e6f0ff",
            width=55,
            height=2
        )

        btn.config(command=lambda: self.select_flight(btn, flight))
        btn.pack(fill="x", pady=5)
            
        self.flight_buttons[flight] = btn


    def select_flight(self, button, flight):
        if self.selected_flight_button:
            self.selected_flight_button.config(bg="#e6f0ff")

        self.selected_flight_button = button
        self.selected_flight_obj = flight
        self.selected_flight = flight.callsign  # só para mensagens

        button.config(bg="#99ccff")
        self.add_log(f"Selected flight: {flight.callsign}")


    def update_flight(self, flight):
        btn = self.flight_buttons.get(flight)
        
        # voo já não está na UI (foi autorizado)
        if not btn or not btn.winfo_exists():
            return

        btn.config(text=f"{flight.callsign} - T-{flight.eta}s")


    def remove_flight(self, flight):
        btn = self.flight_buttons.pop(flight, None)
        if btn:
            btn.destroy()
            self.add_log(f"Voo {flight.callsign} expirou.")


    # -----------------------------------


    def authorize(self):
        if not self.selected_flight or not self.selected_runway:
            self.add_log("Selecione um voo e uma pista primeiro.")
            return

        runway = self.engine.get_runway(self.selected_runway)
        flight = self.selected_flight_obj  

        success = self.engine.assign_flight_to_runway(flight, runway)

        if not success:
            self.add_log(f"Pista {runway.name} está ocupada.")
            return

        # remover voo da queue
        self.selected_flight_button.destroy()

        self.add_log(
            f"Voo {flight.callsign} autorizado para a pista {runway.name}."
        )

        self.engine.flights.remove(flight)

        self.selected_runway_rect = None
        self.selected_runway = None

        self.selected_flight = None
        self.selected_flight_button = None


    def add_log(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.config(state="disabled")
        self.log.see("end")

    def add_system_message(self, msg):
        self.add_log(f"[SYSTEM] {msg}")



