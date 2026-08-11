ALTER TABLE prediction_record ADD COLUMN sporttery_home_handicap INTEGER;
ALTER TABLE prediction_record ADD COLUMN predicted_hhad_outcome TEXT;
ALTER TABLE prediction_record ADD COLUMN predicted_hhad_probability REAL;
ALTER TABLE prediction_record ADD COLUMN actual_hhad_outcome TEXT;
ALTER TABLE prediction_record ADD COLUMN hhad_correct INTEGER;
