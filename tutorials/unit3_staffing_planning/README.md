# Unit 3: Staffing and strategic planning (T7 - T9)

Synthetic hospital data from `hospital_data.py` (3 years of daily ED arrivals; 81,059 inpatient encounters over 6 service lines).

- `t7_staffing_forecast.py`: 7-day-ahead arrival forecast (seasonal-naive vs linear vs gradient boosting) turned into a nurse roster and costed against flat rosters.
- `t8_strategic_planning_descriptive.py`: service-line scorecard (volume, bed-days, ALOS, margin, growth, occupancy) and a growth-vs-margin matrix.
- `t9_strategic_planning_predictive.py`: log-linear trend projection with 80% scenarios, beds needed at 85% occupancy, and a linear programme (scipy HiGHS) that allocates scarce beds to maximise margin, with the shadow price of a bed-day.

Run from this folder: `python t7_staffing_forecast.py`, then `t8_...`, `t9_...`. Outputs go to `outputs/`.
