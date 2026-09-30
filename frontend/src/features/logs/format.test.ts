import {
  fitMono,
  formatClock,
  formatHM,
  formatHours,
  formatLongDate,
  formatMiles,
  splitDate,
  truncate,
  weekdayOf,
} from "./format";

describe("formatHours", () => {
  it.each([
    [10, "10"],
    [1.75, "1.75"],
    [4.5, "4.5"],
    [0, "0"],
    [24, "24"],
    [7.749999, "7.75"],
    [-0, "0"],
  ])("%s -> %s", (input, expected) => {
    expect(formatHours(input)).toBe(expected);
  });
});

describe("formatMiles and formatHM", () => {
  it("rounds to 0.1 and strips .0", () => {
    expect(formatMiles(350)).toBe("350");
    expect(formatMiles(337.7)).toBe("337.7");
    expect(formatMiles(0)).toBe("0");
    expect(formatMiles(1234.56)).toBe("1234.6");
  });

  it("formats H:MM and HH:MM", () => {
    expect(formatHM(1.75)).toBe("1:45");
    expect(formatHM(10)).toBe("10:00");
    expect(formatClock(1440)).toBe("24:00");
    expect(formatClock(75)).toBe("01:15");
  });
});

describe("dates", () => {
  it("splits by string and never shifts the day", () => {
    expect(splitDate("2021-04-09")).toEqual({ mm: "04", dd: "09", yyyy: "2021" });
  });

  it("formats the weekday in UTC", () => {
    expect(weekdayOf("2021-04-09")).toBe("Fri");
    expect(formatLongDate("2021-04-09")).toBe("Fri Apr 9, 2021");
  });

  it.each(["America/Los_Angeles", "Pacific/Kiritimati"])("is stable under TZ=%s", (tz) => {
    const previous = process.env.TZ;
    process.env.TZ = tz;
    try {
      expect(splitDate("2021-04-09").dd).toBe("09");
      expect(formatLongDate("2021-04-09")).toBe("Fri Apr 9, 2021");
    } finally {
      if (previous === undefined) delete process.env.TZ;
      else process.env.TZ = previous;
    }
  });
});

describe("fitMono", () => {
  it("leaves a short string unchanged", () => {
    expect(fitMono("Richmond, VA", 358, 15)).toEqual({
      text: "Richmond, VA",
      size: 15,
      clipped: false,
    });
  });

  it("shrinks a medium string to no less than 80 percent", () => {
    const text = "x".repeat(45); // 45 * 9 = 405 > 358
    const fit = fitMono(text, 358, 15);
    expect(fit.clipped).toBe(true);
    expect(fit.text).toBe(text);
    expect(fit.size).toBeGreaterThanOrEqual(12);
    expect(fit.size).toBeLessThan(15);
    expect(0.6 * fit.size * text.length).toBeLessThanOrEqual(358 + 1e-6);
  });

  it("truncates a long string at the minimum size with three dots", () => {
    const fit = fitMono("y".repeat(80), 358, 15);
    expect(fit.size).toBe(12);
    expect(fit.text).toHaveLength(Math.floor(358 / (0.6 * 12)));
    expect(fit.text.endsWith("...")).toBe(true);
    expect(fit.clipped).toBe(true);
  });

  it("renders nothing for an empty value", () => {
    expect(fitMono("", 358, 15).text).toBe("");
  });

  it("truncate keeps short strings", () => {
    expect(truncate("abc", 5)).toBe("abc");
    expect(truncate("abcdefgh", 6)).toBe("abc...");
  });
});
