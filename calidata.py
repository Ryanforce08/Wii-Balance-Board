import time
import wiibalance

SAMPLES = 30
DELAY = 0.1  # seconds between samples


wii = wiibalance.WiiBalanceBoard()
def read_raw_data():
    """
    Replace this function with your actual code that reads raw sensor values
    from the Wii Balance Board.
    
    Must return a list of 4 integers: [top_left, top_right, bottom_left, bottom_right]
    """
    return wii.get_raw_data()


def get_average_readings(samples):
    sums = [0,0,0,0]
    for sample in samples:
        for i in range(4):
            sums[i] += sample[i]
    return [s / len(samples) for i, s in enumerate(sums)]


def calibrate(zero_avg, known_avg, known_weight):
    zero_offsets = zero_avg
    scale_factors = []
    for zero, known in zip(zero_offsets, known_avg):
        denom = known - zero
        scale = known_weight / denom if denom != 0 else 0.0
        scale_factors.append(scale)
    return zero_offsets, scale_factors


def convert_raw_to_weight(raw, zero_offsets, scale_factors):
    weights = []
    for r, z, s in zip(raw, zero_offsets, scale_factors):
        weight = max(0.0, (r - z) * s)
        weights.append(weight)
    total = sum(weights)
    return weights, total


def sample_readings(num_samples):
    samples = []
    print(f"Starting to sample {num_samples} readings:")
    for i in range(num_samples):
        reading = wii.raw_data
        samples.append(reading)
        print(f"  Sample {i+1}: {reading}")
        time.sleep(DELAY)
    return samples


def main():
    
    print("Wii Balance Board Calibration")
    wii.start_cali()
    print("Starting board reader...")
    time.sleep(1)  # Allow time for board to stabilize
    print("\nStep 1: Ensure NO weight on the board.")
    input("Press Enter when ready...")

    zero_samples = sample_readings(SAMPLES)
    zero_avg = get_average_readings(zero_samples)
    print("\nZero offset readings (no weight):", zero_avg)

    print("\nStep 2: Place a known weight on the board.")
    while True:
        try:
            known_weight = float(input("Enter the known weight in kilograms: "))
            if known_weight > 0:
                break
            else:
                print("Weight must be positive.")
        except ValueError:
            print("Invalid number. Please enter a decimal number.")

    input(f"Place the {known_weight} kg weight on the board and press Enter to start sampling...")

    known_samples = sample_readings(SAMPLES)
    known_avg = get_average_readings(known_samples)
    print("\nKnown weight readings:", known_avg)

    zero_offsets, scale_factors = calibrate(zero_avg, known_avg, known_weight)
    print("\nCalibration complete.")
    print("Zero offsets:", zero_offsets)
    print("Scale factors:", scale_factors)

    print("\nStarting live weight readings. Press Ctrl+C to exit.\n")
    try:
        while True:
            raw = read_raw_data()
            weights, total = convert_raw_to_weight(raw, zero_offsets, scale_factors)
            print(f"Raw: {raw} | Weights: {[round(w,2) for w in weights]} | Total weight: {total:.2f} kg", end='\r')
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nExiting.")

if __name__ == "__main__":
    main()
