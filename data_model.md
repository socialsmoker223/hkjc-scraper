# HKJC 資料模型 (Database Schema)

> **Database Compatibility:** This schema is compatible with both Local PostgreSQL and Supabase (cloud PostgreSQL). The schema design is database-agnostic and uses standard PostgreSQL features.

整個專案目前有 9 張核心表：Meeting、Race、Horse、HorseProfile（現況）、HorseProfileHistory（歷史）、Jockey、Trainer、Runner、HorseSectional。這些表對應 HKJC 的賽事頁、分段時間頁、馬匹資料頁，涵蓋你目前要用的全部資料。[1][2]

***

## 賽日與賽事

**meeting**  
- `id` BIGSERIAL PK  
- `date` DATE — 賽事日期  
- `venue_code` VARCHAR(4) — ST/HV  
- `venue_name` VARCHAR(32) — 沙田 / 跑馬地  
- `source_url` TEXT  
- `season` INT — 賽季起始年 (e.g. 2024 for 24/25)，每年9月開始新賽季

關係：1:N → `race`（一個賽日多場賽事）。[2]

**race**  
- `id` BIGSERIAL PK  
- `meeting_id` BIGINT FK → `meeting.id`  
- `race_no` INT — 當日第幾場  
- `race_code` INT — 全季總場次 (e.g. 284)，每年9月重置為 1  
- `name_cn` VARCHAR(128)  
- `class_text` VARCHAR(32) — 第四班等  
- `distance_m` INT  
- `track_type` VARCHAR(16) — 草地 / 泥地  
- `track_course` VARCHAR(8) — A, A+3, C+3…  
- `going` VARCHAR(32) — 好地等  
- `prize_total` INT — 總獎金 HKD  
- `final_time_str` VARCHAR(16) — 1:34.62 等  
- `localresults_url` TEXT  
- `sectional_url` TEXT  

約束與關係：UNIQUE(`meeting_id`,`race_no`)，1:N → `runner`, `horse_sectional`。[1]

***

## 馬匹與 Profile（含歷史）

**horse**  
- `id` BIGSERIAL PK  
- `code` VARCHAR(16) UNIQUE — J344 等  
- `name_cn` VARCHAR(128)  
- `name_en` VARCHAR(128) NULL  
- `hkjc_horse_id` VARCHAR(32) UNIQUE — HK_2023_J344  
- `profile_url` TEXT  
- `origin` VARCHAR(64)  
- `age` INT  
- `colour` VARCHAR(32)  
- `sex` VARCHAR(16)  
- `import_type` VARCHAR(64)  
- `season_prize_hkd` INT  
- `lifetime_prize_hkd` INT  
- `record_wins` INT  
- `record_seconds` INT  
- `record_thirds` INT  
- `record_starts` INT  
- `last10_starts` INT  
- `current_location` VARCHAR(64)  
- `current_location_date` DATE NULL  
- `import_date` DATE NULL  
- `owner_name` VARCHAR(128)  
- `current_rating` INT NULL  
- `season_start_rating` INT NULL  
- `sire_name` VARCHAR(128)  
- `dam_name` VARCHAR(128)  
- `dam_sire_name` VARCHAR(128)  

關係：1:N → `runner`, `horse_sectional`, 1:N → `horse_profile_history`。[3]

**horse_profile_history**（每次更新一筆快照）  
- `id` BIGSERIAL PK  
- `horse_id` BIGINT FK → `horse.id`  
- `captured_at` TIMESTAMPTZ — 抓取時間  
- 其餘欄位同 `horse` profile 欄位：  
  - `origin`, `age`, `colour`, `sex`, `import_type`,  
  - `season_prize_hkd`, `lifetime_prize_hkd`,  
  - `record_wins`, `record_seconds`, `record_thirds`, `record_starts`,  
  - `last10_starts`, `current_location`, `current_location_date`, `import_date`,  
  - `owner_name`, `current_rating`, `season_start_rating`,  
  - `sire_name`, `dam_name`, `dam_sire_name`  

索引建議：INDEX(`horse_id`, `captured_at` DESC)，UNIQUE(`horse_id`, `captured_at`)。這張表保留所有歷史 profile 版本，用來追蹤評分、獎金、owner 等變化。[5][6]

***

## 騎師與練馬師

**jockey**
- `id` BIGSERIAL PK
- `code` VARCHAR(16) UNIQUE NULL — 由 `JockeyId` 抽出（舊賽事可能無 code）
- `name_cn` VARCHAR(64) UNIQUE NOT NULL — 主鍵識別欄位
- `name_en` VARCHAR(64) NULL

**trainer**
- `id` BIGSERIAL PK
- `code` VARCHAR(16) UNIQUE NULL — 由 `TrainerId` 抽出（舊賽事可能無 code）
- `name_cn` VARCHAR(64) UNIQUE NOT NULL — 主鍵識別欄位
- `name_en` VARCHAR(64) NULL

兩者來自 LocalResults 成績表中的騎師及練馬師欄位超連結與文字。`name_cn` 作為唯一識別鍵，因為舊賽事資料可能沒有 URL 連結（無 code）。[2]

***

## 每場每馬成績與分段

**runner**（每場每馬一筆）  
- `id` BIGSERIAL PK  
- `race_id` BIGINT FK → `race.id`  
- `horse_id` BIGINT FK → `horse.id`  
- `jockey_id` BIGINT FK → `jockey.id`  
- `trainer_id` BIGINT FK → `trainer.id`  
- `finish_position_raw` VARCHAR(8) — 1, 2, PU 等  
- `finish_position_num` INT NULL — 數字名次  
- `horse_no` INT — 鞍號  
- `actual_weight` INT NULL  
- `declared_weight` INT NULL  
- `draw` INT NULL  
- `margin_raw` VARCHAR(16)  
- `running_pos_raw` VARCHAR(64) — 例如「3 1-1/2 24.69」會另存到 sectional，這裡保留 summary 跑位欄位字串  
- `finish_time_str` VARCHAR(16)  
- `win_odds` DECIMAL(8,2) NULL  

約束：UNIQUE(`race_id`, `horse_id`)。該表對應 LocalResults 的成績主表。[2]

**horse_sectional**（每場每馬每段一筆）  
- `id` BIGSERIAL PK  
- `race_id` BIGINT FK → `race.id`  
- `runner_id` BIGINT FK → `runner.id`  
- `horse_id` BIGINT FK → `horse.id`  
- `section_no` INT — 1..N（由分段時間表 header「第x段」計算）  
- `position` INT NULL — 段內位置  
- `margin_raw` VARCHAR(16) NULL — 段末距離字串  
- `time_main` DECIMAL(6,2) NULL — 主段時間（如 23.41）  
- `time_sub1` DECIMAL(6,2) NULL  
- `time_sub2` DECIMAL(6,2) NULL  
- `time_sub3` DECIMAL(6,2) NULL  
- `finish_time_str` VARCHAR(16) — 全場時間，用來與 runner 對齊  
- `raw_cell` VARCHAR(64) — 原始 cell 文本，例如「3 1-1/2 23.57 11.87 11.70」  

約束：UNIQUE(`runner_id`, `section_no`)。該表直接展開 DisplaySectionalTime 表中每匹馬的「各段走位與分段時間」。[7][1]

***

整體關係總結：  

- `meeting` 1:N `race`  
- `race` 1:N `runner`  
- `horse` 1:N `runner`, 1:N `horse_sectional`, 1:(1+N) `horse_profile` / `horse_profile_history`  
- `jockey`, `trainer` 1:N `runner`  
- `runner` 1:N `horse_sectional`  

這套模型覆蓋你目前要抓的 LocalResults、DisplaySectionalTime、馬匹資料三類頁面，並已把 horse_profile 歷史拆成獨立表方便追蹤變化。[4][7][2]

[1](https://racing.hkjc.com/racing/information/chinese/Racing/DisplaySectionalTime.aspx?RaceDate=20/12/2025&RaceNo=7)
[2](https://racing.hkjc.com/racing/information/English/Racing/LocalResults.aspx)
[3](https://racing.hkjc.com/racing/information/english/Horse/SelectHorse.aspx)
[4](https://racing.hkjc.com/racing/information/english/Horse/HorseFormerName.aspx)
[5](https://racing.hkjc.com/racing/information/English/Horse/LatestOnHorse.aspx?View=Horses%2Fclas%2F)
[6](https://racing.hkjc.com/racing/information/english/Horse/LatestOnHorse.aspx?View=Horses%2Fcsum)
[7](https://racing.hkjc.com/racing/information/English/Racing/DisplaySectionalTime.aspx?RaceDate=29%2F12%2F2019&RaceNo=7)
