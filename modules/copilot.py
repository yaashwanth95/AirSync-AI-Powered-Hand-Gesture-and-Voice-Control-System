def analyze_telemetry(data):
    data = data or {}
    core_temp = data.get("coolantTemp", 589)
    pressure = data.get("reactorCoolantPressure", 2235)
    flow = data.get("rcsFlow", 98.2)
    scram_active = data.get("scramActive", False)
    active_scenario = data.get("activeScenario", "")
    alarm_count = data.get("alarmCount", 0)
    
    health = 100
    
    if scram_active:
        health = 25
        status_desc = "EMERGENCY SHUTDOWN (SCRAM) IN PROGRESS"
        risk_level = "HIGH"
        risk_score = 75
        fail_prob = 10.0
        recommendations = [
            "• Monitor Core Subcooling Margin.",
            "• Verify all Control Rods are fully inserted (0%).",
            "• Maintain emergency boron injection if subcriticality margin is low."
        ]
        explanation = "Reactor SCRAM was manually or automatically initiated. Thermal power is decreasing rapidly, and rods are fully inserted. Decay heat must be managed via residual heat removal systems."
    else:
        temp_deviation = abs(core_temp - 589)
        if temp_deviation > 10:
            health -= int((temp_deviation - 10) * 1.5)
        
        press_deviation = abs(pressure - 2235)
        if press_deviation > 50:
            health -= int((press_deviation - 50) * 0.2)
            
        if flow < 95.0:
            health -= int((95.0 - flow) * 1.8)
            
        health -= alarm_count * 4
        
        if active_scenario:
            health -= 15
            
        health = max(0, min(100, health))
        
        if health >= 90:
            risk_level = "LOW"
            risk_score = max(0, 100 - health)
            fail_prob = round((100 - health) * 0.1, 1)
            status_desc = "SYSTEMS IN NOMINAL STEADY STATE"
            recommendations = [
                "• Maintain steady state nominal power.",
                "• Continue standard logs and inspections."
            ]
            explanation = "All core thermodynamic and hydraulic parameters are within the green band. Control rod banks are at expected heights, and flow rate is stable."
        elif health >= 70:
            risk_level = "MEDIUM"
            risk_score = 100 - health
            fail_prob = round((100 - health) * 0.8, 1)
            
            if "Pump" in active_scenario:
                status_desc = "DEGRADED CORE FLOW COMPROMISING HEAT TRANSFER"
                recommendations = [
                    "• Increase Loop 1 / Loop 2 Flow control knobs to compensate.",
                    "• Verify secondary primary coolant pump switch is enabled.",
                    "• Check coolant pump electrical bus voltages."
                ]
                explanation = f"Primary coolant pump failure has reduced loop flow rate to {flow}%. Core temperature is rising, and risk model indicates localized boiling possibility if flow is not restored."
            elif "Leak" in active_scenario:
                status_desc = "PRIMARY COOLANT DEPRESSURIZATION WARNING"
                recommendations = [
                    "• Engage Safety Injection system switches.",
                    "• Isolate primary loop leak path if possible.",
                    "• Monitor Pressurizer Level knob to verify margin."
                ]
                explanation = f"Primary loop pressure has dropped to {pressure} psia. A coolant leak is suspected. ECCS actuation is imminent if pressure falls below safety threshold."
            elif "Grid" in active_scenario:
                status_desc = "ELECTRICAL GRID FREQUENCY INSTABILITY"
                recommendations = [
                    "• Adjust Turbine Bypass valve setting to stabilize load.",
                    "• Trim control rod positions to manage thermal power output.",
                    "• Monitor generator frequency output."
                ]
                explanation = "Grid frequency is fluctuating wildly, causing turbine-generator load mismatches. Thermal power must be adjusted to prevent generator trip."
            else:
                status_desc = "SYSTEM STABILITY DEGRADED"
                recommendations = [
                    "• Reduce Power Setpoint to 80%.",
                    "• Verify control rod positions match thermal output.",
                    "• Check feedwater flow balance."
                ]
                explanation = f"Reactor health has decreased to {health}%. Temperature or pressure deviations are exceeding nominal limits. Operators should monitor core variables closely."
        else:
            risk_level = "HIGH"
            risk_score = 100 - health
            fail_prob = round((100 - health) * 1.2, 1)
            fail_prob = min(99.9, fail_prob)
            
            if "Runaway" in active_scenario:
                status_desc = "CRITICAL: THERMAL RUNAWAY IN CORE"
                recommendations = [
                    "• INITIATE MANUAL SCRAM IMMEDIATELY.",
                    "• Fully insert all control rod banks.",
                    "• Initiate emergency boration to maximum ppm."
                ]
                explanation = f"Core thermal runaway is in progress! Temperature has surged to {core_temp} deg F. Fuel centerline temperature is approaching safety limits. Immediate SCRAM required to prevent cladding damage."
            elif "Leak" in active_scenario:
                status_desc = "CRITICAL: LOCA (LOSS OF COOLANT ACCIDENT)"
                recommendations = [
                    "• Verify ECCS injection is at maximum flow.",
                    "• Execute emergency reactor SCRAM.",
                    "• Monitor containment pressure and trigger containment spray."
                ]
                explanation = f"Severe loss of coolant accident (LOCA). Coolant pressure is dangerously low at {pressure} psia. Emergency core cooling systems must be manually verified. Execute SCRAM immediately."
            elif "Spike" in active_scenario:
                status_desc = "CRITICAL: PRIMARY SYSTEM OVERPRESSURE"
                recommendations = [
                    "• Open Pressurizer Relief Valve.",
                    "• Engage Containment Spray system.",
                    "• Reduce power setpoint and insert rods."
                ]
                explanation = f"RCS Pressure has spiked dangerously to {pressure} psia. Relief valves must be opened to prevent structural integrity failure of the reactor vessel."
            else:
                status_desc = "CRITICAL LIMIT EXCEEDED"
                recommendations = [
                    "• Prepare for manual reactor SCRAM.",
                    "• Verify auxiliary feedwater pumps are running.",
                    "• Ensure control room alerts are acknowledged."
                ]
                explanation = f"Reactor parameters are critically out of range. Health score is at {health}%. Immediate intervention required to prevent automatic reactor trip."

    return {
        "health": health,
        "riskLevel": risk_level,
        "riskScore": risk_score,
        "failProbability": fail_prob,
        "statusDesc": status_desc,
        "recommendations": recommendations,
        "explanation": explanation
    }
