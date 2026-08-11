"""Capture the demo GIF by walking the app end to end in a headless browser.

Usage (with backend on :5000 and frontend on :3000):
    python docs/capture_demo.py
"""
import os
import time

from PIL import Image
from playwright.sync_api import sync_playwright

OUT_DIR = "docs/_frames"
GIF = "docs/demo.gif"
RESUME = os.path.abspath("docs/sample_resume.pdf")
W, H = 1150, 720

JD = ("Backend Engineer (Junior). Required: Python, Flask, REST API, MySQL, "
      "Redis, Docker, AWS. Nice to have: Kafka, system design, unit testing.")

ANSWER = ("I used a Redis write-through cache keyed on account id. Hit ratio settled "
          "around 92%, and I invalidated on write so balances never went stale. That "
          "cut p99 from 120ms to about 70ms because we stopped re-reading the DB on "
          "every lookup.")

frames = []


def shot(page, name, hold=1):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = f"{OUT_DIR}/{len(frames):02d}_{name}.png"
    page.screenshot(path=path)
    for _ in range(hold):
        frames.append(path)
    print("  frame:", name)


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H},
                                device_scale_factor=1)

        print("1. landing")
        page.goto("http://localhost:3000", wait_until="networkidle")
        page.wait_for_timeout(1200)
        shot(page, "landing", hold=3)

        print("2. select resume")
        page.set_input_files("input[type=file]", RESUME)
        page.wait_for_timeout(700)
        shot(page, "selected", hold=3)

        print("3. upload + report (embedding model may take a while)")
        page.click("text=Start interview")
        page.wait_for_selector("text=Parsing Safety Score", timeout=180000)
        page.wait_for_timeout(1500)
        shot(page, "report_top", hold=3)

        # scroll through the report
        page.mouse.wheel(0, 520)
        page.wait_for_timeout(900)
        shot(page, "report_claims", hold=3)

        print("4. job description match")
        page.fill("textarea", JD)
        page.wait_for_timeout(400)
        page.click("text=Check fit")
        page.wait_for_selector("text=Job Description Match", timeout=180000)
        page.wait_for_timeout(1200)
        page.mouse.wheel(0, 300)
        page.wait_for_timeout(600)
        shot(page, "jd_match", hold=4)

        print("5. start interview")
        page.get_by_role("button", name="Start").last.click()
        page.wait_for_selector("text=Interviewer", timeout=240000)
        page.wait_for_timeout(2500)          # let the typewriter finish
        shot(page, "question", hold=4)

        print("6. type an answer")
        page.fill("#answer", ANSWER)
        page.wait_for_timeout(600)
        shot(page, "answer", hold=3)

        print("7. feedback")
        page.click("text=Submit answer")
        page.wait_for_selector(".feedback", timeout=180000)
        page.wait_for_timeout(1800)
        page.mouse.wheel(0, 320)
        page.wait_for_timeout(600)
        shot(page, "feedback", hold=5)

        browser.close()

    print("assembling gif...")
    imgs = [Image.open(f).convert("P", palette=Image.ADAPTIVE, colors=180)
            for f in frames]
    imgs[0].save(GIF, save_all=True, append_images=imgs[1:],
                 duration=650, loop=0, optimize=True)
    print("wrote", GIF, f"({os.path.getsize(GIF)/1024/1024:.1f} MB)")


if __name__ == "__main__":
    run()
