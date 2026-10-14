"""Explicit PostgreSQL types for current linelist headings."""
from header_mapping import TARGET

INTEGERS = set('Ageatstartofart Ageinmonths DaysOnART DaysOfARVRefill Current_Age CurrentAge_Months INHDaysOfARVRefill Days_To_Schedule Recapture_count'.split())
DECIMALS = set('CurrentViralLoad LastWeight LastHeight BMI FirstCD4'.split())
DATES = set('''HIVConfirmedDate ARTStartDate Pharmacy_LastPickupdate
Pharmacy_LastPickupdate_PreviousQuarter Clinic_Visit_Lastdate LastPickupDateCal
DateDevolved DateofCurrentViralLoad DateResultReceivedFacility LastDateOfSampleCollection
Outcomes_Date DOB Date_Transfered_In LastWeightDate DateofFirstTLD_Pickup FirstCD4Date
EstimatedNextAppointmentPharmacy Next_Ap_by_pharmPill Next_Ap_by_careCard
TB_Screening_Date TPT_Startdate TPT_Completion_date TPTOutcomeDate DateofCurrent_TBStatus
TBTreatmentStartDate TBTreatmentStopDate Date_Enrolled_Into_OTZ OTZ_Outcome_Date
Next_Visit_Date'''.split())
DATES.update('Date_Generated PBSDateCreated RecapturedDate'.split())
TIMESTAMPS = set()
TYPES = {h: 'integer' if h in INTEGERS else 'numeric' if h in DECIMALS else 'date' if h in DATES
         else 'timestamp without time zone' if h in TIMESTAMPS else 'text' for h in TARGET}


SAFE_CAST_BODY = r'''
DECLARE cleaned text; parsed numeric; date_value date; timestamp_value timestamp;
BEGIN
    IF val IS NULL OR btrim(val) = '' THEN RETURN NULL; END IF;
    cleaned := btrim(val);
    IF kind = 'integer' THEN
        IF cleaned !~ '^[+-]?[0-9]+([.]0+)?$' THEN RETURN NULL; END IF;
        parsed := cleaned::numeric;
        IF parsed < -2147483648 OR parsed > 2147483647 THEN RETURN NULL; END IF;
        RETURN (parsed::integer)::text;
    ELSIF kind = 'numeric' THEN
        IF cleaned !~ '^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?$' THEN RETURN NULL; END IF;
        RETURN (cleaned::numeric)::text;
    ELSIF kind = 'date' OR kind = 'timestamp without time zone' THEN
        -- ISO only: ambiguous locale-specific dates and Excel serials are flagged.
        IF cleaned !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}([ T][0-9]{2}:[0-9]{2}(:[0-9]{2}([.][0-9]+)?)?)?$' THEN RETURN NULL; END IF;
        timestamp_value := cleaned::timestamp;
        IF kind = 'date' THEN RETURN (timestamp_value::date)::text; END IF;
        RETURN timestamp_value::text;
    END IF;
    RETURN val;
EXCEPTION WHEN invalid_text_representation OR datetime_field_overflow
    OR numeric_value_out_of_range OR invalid_datetime_format THEN
    RETURN NULL;
END
'''
