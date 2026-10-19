# Laptop Shopping Benchmark

Evaluation benchmark testing an agent's multi-criteria reasoning, domain-specific trade-off analysis, hardware specification comprehension, and ability to handle edge cases where the correct answer is `ALL` or `NONE`.

## Overview

Given a JSON input list of 10 laptop specifications with pictures and a user persona, the model must determine which laptop best satisfies the persona's constraints and priorities, or respond with `ALL` or `NONE`.

- **Catalog schema**: [`fixtures/laptops/schema.json`](../fixtures/laptops/schema.json)
- **Laptop catalog**: [`fixtures/laptops/catalog.json`](../fixtures/laptops/catalog.json)
- **Task definitions**: [`tasks/laptop-shopping.json`](../tasks/laptop-shopping.json)
- **Offline grader & prompt builder**: [`suites/laptop_shopping/grader.py`](../suites/laptop_shopping/grader.py)
- **Inspect AI task**: [`suites/laptop_shopping/task.py`](../suites/laptop_shopping/task.py)
- **Unit tests**: [`tests/test_laptop_shopping.py`](../tests/test_laptop_shopping.py)

---

## The 10-Laptop Catalog

The catalog combines the 5 user-provided configurations with 5 top recommendations from *Wirecutter* guides to form a comprehensive, realistic hardware comparison set:

| # | ID | Name | Screen | CPU / GPU | RAM / Storage | Weight & Battery | Price | Source / Reference |
|---|---|---|---|---|---|---|---|---|
| 1 | `acer_aspire_16_a16_71m` | Acer Aspire 16 (A16-71M-593C) | 16" 1920x1200 IPS 60Hz | Intel Core Ultra 5 115U / Intel Graphics | 16GB LPDDR5X / 512GB SSD | 3.60 lbs / 10h (65 Wh) | $649.99 | [Walmart](https://www.walmart.com/ip/Acer-Aspire-16-WUXGA-1920-x-1200-Window-Laptop-16GB-RAM-512GB-SSD-Intel-Core-Ultra-5-Intel-Graphics-A16-71M-593C-Steel-Gray/18143224660) |
| 2 | `apple_macbook_pro_14_m5_pro` | Apple MacBook Pro 14.2" (M5 Pro) | 14.2" 3024x1964 Mini-LED 120Hz | Apple M5 Pro (15-core CPU, 16-core GPU) | 24GB Unified / 1TB SSD | 3.52 lbs / 18h (72.4 Wh) | $2,069.10 | [Amazon (B0GR1JK9W3)](https://www.amazon.com/gp/product/B0GR1JK9W3) |
| 3 | `framework_laptop_13_amd_ai300` | Framework Laptop 13 (AMD Ryzen AI 300) | 13.5" 2880x1920 IPS 120Hz (3:2) | AMD Ryzen AI 7 360 / Radeon 880M | 32GB DDR5 (SO-DIMM) / 1TB SSD | 2.86 lbs / 14h (61 Wh) | $1,299.00 | [Framework](https://frame.work/products/laptop13-amd-ai300/configuration/new) |
| 4 | `apple_macbook_air_13_m5` | Apple MacBook Air 13" (M5, Sky Blue) | 13.6" 2560x1664 Retina 60Hz | Apple M5 (10-core CPU, 10-core GPU) | 16GB Unified / 512GB SSD | 2.70 lbs / 18h (52.6 Wh) | $1,256.00 | [Amazon (B0GR1493ZV)](https://www.amazon.com/dp/B0GR1493ZV/) |
| 5 | `gigabyte_gaming_a16_rtx5060` | Gigabyte Gaming A16 (i7-13620H, RTX 5060) | 16" 1920x1200 IPS 165Hz | Intel Core i7-13620H / RTX 5060 (8GB) | 32GB DDR5 / 1TB SSD | 4.85 lbs / 5h (76 Wh) | $1,199.99 | [Best Buy (J3GWPQC2TJ)](https://www.bestbuy.com/product/gigabyte-gaming-a16-16-165hz-1920x1200-wuxga-intel-core-i7-13620h-1tb-ssd-32gb-ddr5-ram-geforce-rtx-5060-black-steel/J3GWPQC2TJ) |
| 6 | `asus_chromebook_plus_cx34` | Asus Chromebook Plus CX34 | 14" 1920x1080 IPS 60Hz | Intel Core i3-1315U / Intel UHD | 8GB LPDDR5 / 128GB UFS | 3.17 lbs / 10.5h (50 Wh) | $399.99 | Wirecutter Best Budget Chromebook |
| 7 | `asus_rog_zephyrus_g14` | Asus ROG Zephyrus G14 (RTX 5070) | 14" 2880x1800 OLED 120Hz | AMD Ryzen AI 9 HX 370 / RTX 5070 (8GB) | 32GB LPDDR5X / 1TB SSD | 3.31 lbs / 10h (73 Wh) | $2,199.99 | Wirecutter Best Portable Gaming Laptop |
| 8 | `lenovo_yoga_7i_14` | Lenovo Yoga 7i 2-in-1 14" (Core Ultra 5) | 14" 1920x1200 OLED Touch 360° | Intel Core Ultra 5 125U / Intel Arc | 16GB LPDDR5X / 512GB SSD | 3.04 lbs / 16.5h (71 Wh) | $849.99 | Wirecutter Best Windows Laptop for Most People |
| 9 | `lenovo_yoga_pro_9i_16` | Lenovo Yoga Pro 9i 16" (Ultra 9, RTX 5060) | 16" 3200x2000 OLED 165Hz (Adobe RGB) | Intel Core Ultra 9 285H / RTX 5060 (8GB) | 32GB LPDDR5X / 1TB SSD | 4.25 lbs / 11h (84 Wh) | $1,899.99 | Wirecutter Best Video & Photo Editing Windows Laptop |
| 10 | `asus_expertbook_p5_14` | Asus ExpertBook P5 (Core Ultra 7 258V) | 14" 2560x1600 IPS 144Hz | Intel Core Ultra 7 258V / Intel Arc 140V | 32GB LPDDR5X / 1TB SSD | 2.78 lbs / 16.5h (63 Wh) | $1,099.99 | Wirecutter Best Business Laptop |

---

## Schema Structure

The schema adheres to JSON Schema Draft 2020-12 and mandates:
- **Identification & Pricing**: `id`, `name`, `brand`, `model_number`, `price_usd`, `source_url`.
- **Pictures (`images`)**: Array with URL, textual description, and `view_type` (`front`, `angled`, `keyboard`, `ports`, `open`, `profile`).
- **Display (`screen`)**: Size, resolution, aspect ratio, refresh rate, panel type, touchscreen boolean, brightness in nits.
- **Physical Specs**: Dimensions (width, depth, thickness, formatted string) and `weight_lbs`.
- **Battery**: Capacity in watt-hours (`capacity_wh`) and real-world runtime (`estimated_life_hours`).
- **Core Hardware**: Processor (model, cores, architecture, NPU TOPS), RAM (capacity, type, upgradability), Storage (capacity, type, upgradability), and Graphics (GPU name, integrated vs discrete, VRAM).
- **I/O & Special Features**: Ports array, webcam specifications, and notable platform capabilities.

---

## Personas & Expected Answers

| Case ID | Persona Description | Expected Answer | Key Reasoning & Distinguishing Factors |
|---|---|---|---|
| `persona_1_high_school_student` | High school student, needs basic notes, won't crash, cheap as possible. Writing, occasional presentation, web browsing. | `asus_chromebook_plus_cx34` | At $399.99, it is the cheapest laptop by over $240. ChromeOS is sandboxed, stable, boots instantly, runs Google Docs/Slides, and features MIL-STD 810H durability. |
| `persona_2_college_cs_student` | College CS student - needs good Linux support, performant to compile code, not doing game development. | `framework_laptop_13_amd_ai300` | Official Tier-1 Linux certification (Ubuntu/Fedora partner), open EC firmware, fast 8-core Zen 5 CPU, up to 96GB upgradable RAM, modular ports, no discrete GPU penalty. |
| `persona_3_video_editor_premiere` | Video editor - working professional that needs something that runs Adobe Premiere well and has good monitor output options. | `lenovo_yoga_pro_9i_16` | Discrete RTX 5060 with NVIDIA Studio CUDA/NVENC encoding, calibrated 3.2K Adobe RGB screen, HDMI 2.1, Thunderbolt 4, and full-size SD card slot for camera ingest. |
| `persona_4_video_editor_final_cut_pro` | Video editor - needs something that runs Final Cut Pro well. | `apple_macbook_pro_14_m5_pro` | Final Cut Pro only runs on macOS (ruling out 8 PCs). Active cooling prevents thermal throttling during 4K/8K renders (unlike fanless Air), ProRes hardware engines, XDR display. |
| `persona_5_budget_gamer` | Gamer - dedicated GPU, high refresh rate display, portability comes second to performance, good value for money. | `gigabyte_gaming_a16_rtx5060` | High gaming performance per dollar ($1,199.99), RTX 5060 discrete GPU, 165Hz screen, 32GB RAM; 4.85 lbs thick chassis and 5h battery life are acceptable trade-offs. |
| `persona_6_portable_gamer_premium` | Gamer that wants something portable AND performant, money is no issue. | `asus_rog_zephyrus_g14` | Ultra-portable gaming flagship ($2,199.99): weighs just 3.31 lbs and 0.63" thin with RTX 5070 discrete graphics, 120Hz 3K OLED ROG Nebula display, and Ryzen AI 9 CPU. |
| `persona_7_fashionable_student_non_windows` | College student that wants something fashionable that can handle daily tasks well. Not technical, doesn't like Windows. | `apple_macbook_air_13_m5` | macOS (no Windows), iconic Sky Blue unibody, 0.44" thin, 2.70 lbs, completely silent fanless operation, 18-hour battery life. |
| `persona_8_ai_engineer_128b_llm` | AI engineer that needs something that can run intelligent, local LLMs in the 128B range. | `NONE` | A 128B model requires ≥65–75 GB VRAM at 4-bit (and >250 GB at FP16). The maximum RAM on any catalog laptop is 32GB (or 24GB Unified Memory). None can run it locally. |
| `persona_9_elderly_person_lightweight_support` | Elderly person with back issues. Not technical, easy and lightweight, good tech support. | `apple_macbook_air_13_m5` | Lightest laptop in catalog at 2.70 lbs (relieves back issues), simple virus-resilient macOS, and backed by Apple's free walk-in Genius Bar support network nationwide. |
| `persona_10_audiophile_best_audio` | Audiophile who cares about having the best quality audio. | `apple_macbook_pro_14_m5_pro` or `apple_macbook_air_13_m5` or `ALL` | **Conditional Rule**: MacBooks pass if response notes the integrated DAC matching Apple dongle reference quality / high impedance; `ALL` passes if response notes using an external USB DAC. |
| `trick_all_basic_cloud_remote_work` | Remote worker needing ≥8GB RAM, webcam, modern Wi-Fi, Google Docs web editing. | `ALL` | Every single laptop in the catalog meets or exceeds 8GB RAM, has an integrated webcam, supports Wi-Fi 6/6E/7, and runs a modern browser for cloud office suites. |
| `trick_none_submersible_optical_drive` | Marine researcher needing IP68 submersible waterproofing and internal optical Blu-ray drive. | `NONE` | No laptop in the catalog is IP68 waterproof submersible, and none includes an internal optical disc drive. |
| `trick_all_commuter_under_5_5_lbs` | Commuter looking for any laptop under 5.5 lbs with ≥1080p display and ≥128GB storage. | `ALL` | All 10 laptops weigh under 5.5 lbs (heaviest is 4.85 lbs), have resolutions from 1080p to 3.2K, and have between 128GB and 1TB storage. |

---

## Grading & Verification

Run the test suite:
```bash
.venv/bin/python -m unittest tests/test_laptop_shopping.py
```

Run offline grading against model responses:
```bash
.venv/bin/python -m suites.laptop_shopping.grader /path/to/responses.json
```
