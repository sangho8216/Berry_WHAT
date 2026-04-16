graph TD
    subgraph Engine [Engine: System Core]
        AI[AI Interface]
        DB[(Database)]
        Rules[Cultivation Recipes]
        Control[Control Logic]
    end

    subgraph Control_Detail [Control Modules]
        Soil[Soil Environment: Irrigation]
        Air[Atmospheric Environment: Shading/Vents/Fog/Heating]
        Future[Backlog: Photosynthesis/Growth Stage]
    end

    subgraph Signal [Interface Layer: Connectivity]
        Collector[Data Collector]
        Modbus[Modbus Interface]
    end

    subgraph Web [Web: User Interface]
        Monitor[Real-time Monitoring]
        Config[Recipe Configuration]
        Report[Analytics: Sensing & Actuation Logs]
    end

    %% Connection Flow
    Signal --> DB
    Rules --> Control
    Control --> Control_Detail
    Control_Detail --> Signal
    AI <--> DB
    DB <--> Web
