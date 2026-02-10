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
    def __init__(self, root):
        self.root = root
        self.root.title("ATC Simulator")
        self.root.geometry("1450x820")

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

    # ---------------------------
    def draw_runways(self):
        lane_height = 130
        spacing = 35
        y = 20

        for name in ["A", "B", "C"]:
            self.canvas.create_rectangle(60, y, 750, y + lane_height,
                                         fill="#b3ffb3", outline="black", width=2)
            self.canvas.create_text(80, y + lane_height/2,
                                    text=f"Runway {name}", anchor="w",
                                    font=("Arial", 16, "bold"))
            y += lane_height + spacing

    # ---------------------------

    def add_flight(self, flight):
        text = f"{flight.callsign} - ETA {flight.eta}s"
        self.add_flight_button(text)


    def add_flight_button(self, text):
        btn = tk.Button(
            self.scroll.scrollable_frame,
            text=text,
            font=("Arial", 14),
            relief="raised",
            bg="#e6f0ff",
            width=55,  # reduzido para caber melhor
            height=2,
            command=lambda t=text: self.select_flight(t)
        )
        btn.pack(fill="x", pady=5)

    def select_flight(self, flight):
        self.add_log(f"Selected flight: {flight}")

    def authorize(self):
        self.add_log("Authorization sent.")

    def add_log(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.config(state="disabled")
        self.log.see("end")

    def add_system_message(self, msg):
        self.add_log(f"[SYSTEM] {msg}")



