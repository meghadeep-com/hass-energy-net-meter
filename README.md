# Roy's Net Meter Home Assistant Integration

----

**IT MIGHT BE POSSIBLE TO REPLACE THIS INTEGRATION WITH TEMPLATE SENSORS, I'M LOOKING INTO THAT POSSIBILITY, BUT IF YOU HAVE IDEAS, PLEASE FEEL FREE TO CONTRIBUTE!**

----

This is a very niche integration that is applicable only to a handful of users. Since I developed it primarily for my personal use, it uses a lot of assumptions that may not be suitable for any other users.

During setup you choose one of two meter types:

## Option A: Net grid meter

- You have a specific type of "smart" _net meter_ that indicates the **net** energy flow through your meter, which means: **Your meter indicates your imported energy with the pulses when your consumption exceeds generation, and your exported energy with the pulses when your generation exceeds consumption.**
- You have a ESPhome device (essentially a slightly modified Home Assistant Glow) hooked up to your net meter that measures your W, kWh, Var, and kVarh (Var, and kVarh are optional, just the entity built for recording this will record 0) net flow power and energy.
- You have another sensor that measures your consumption current, i.e. the amperage of the main line that enters your home.
- You have generation power data, generated energy data, and the AC amereage of your generation, i.e., the AC amereage of your inverter output.

### Why don't you calculate consumption directly, if you already have a CT clamp?

- CT clamps can be inaccurate even after calibration. And reducing that calibration error needs a lot of trial and error that I don't want to spend time on.
- CT clamps (and a votlmeter) can only measure the total apparent power and energy usage, but I only get billed for my real energy usage. This is why I also measure my kVarh flow through my meter. Using the Var, and kVarh data in the quadratic equation will give me my real power and energy use using CT clamps, but I still would need to calibrate it properly for accuracy.
- By delgating all calculations to the official meter, and using the CT clamp to measure only the amperage of your main line to decide if you are importing or exporting has the benefit of increased accuracy without much calibration work. The only time this calculation will introduce errors is when your solar generation ramps up or down near your consumption, which for a normal household means small inaccuracies only twice a day, not lasting more than 5 minutes in total.

## Option B: Consumption meter

- You have a device that directly reports your home's total power and energy consumption — for example a metering RCBO/breaker — instead of the net flow through the grid connection.
- You have generation power data and generated energy data from your inverter.
- Import/export is derived by comparing your reported consumption against your generation: when consumption exceeds generation you're importing the difference, and when generation exceeds consumption you're exporting it. No CT clamps or current sensors are needed for this option, since consumption is already measured directly.

## How to set it up:

- Add this repository as a custom repository in HACS (category: Integration), then install "Roy's Net Meter" from there. Alternatively, copy `custom_components/roys-net-meter` into your Home Assistant `custom_components` directory manually.
- During setup, pick whether you have a net grid meter or a consumption meter, then select the entities the form asks for.
