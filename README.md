# Roy's Net Meter Home Assistant Integration

---

This is a very niche integration that is applicable only to a handful of users. Since I developed it primarily for my personal use, it uses a lot of assumptions that may not be suitable for any other users.

## Asumptions:

- You have a specific type of "smart" _net meter_ that indicates the **net** energy flow through your meter, which means: **Your meter indicates your imported energy with the pulses when your consumption exceeds generation, and your exported energy with the pulses when your generation exceeds consumption.**
- You have a ESPhome device (essentially a slightly modified Home Assistant Glow) hooked up to your net meter that measures your W, kWh, Var, and kVarh (Var, and kVarh are optional, just the entity built for recording this will record 0) net flow power and energy.
- You have another sensor that measures your consumption current, i.e. the ampereage of the main line that enters your home.
- You have generation power data, generated energy data, and the AC amereage of your generation, i.e., the AC amereage of your inverter output.

## How to set it up:

- This should be working with HACS, but it's not, so I have set it up by copying the files over in the custom_components directory of my Home Assistant integration. Please create a PR if you want it to be supported with HACS, otherwise this workflow works for my personal needs.
- Enter the entity IDs that this integration asks for.
