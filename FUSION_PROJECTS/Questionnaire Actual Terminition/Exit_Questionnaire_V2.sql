SELECT
  PAPF.PERSON_NUMBER                                 EMPLOYEE_ID, 
  PPNF.DISPLAY_NAME                                  FULL_NAME,
  PJFT.NAME                                          JOB_TITLE,
  MGR_NAME.DISPLAY_NAME                              MANAGER_NAME,
  PD.NAME                                            DEPARTMENT, 
  TO_CHAR(PPOS.DATE_START,'YYYY-MM-DD')	             HIRE_DATE ,
  TO_CHAR(PPOS.ACTUAL_TERMINATION_DATE,'YYYY-MM-DD') LAST_WORKING_DATE,
  PART.ACTION_REASON                                 TERMINATION_REASON ,
  PATL.ACTION_NAME                                   TERMINATION_ACTION ,
  HRL.LOCATION_NAME,
   CASE 
    WHEN PPOS.ACTUAL_TERMINATION_DATE IS NOT NULL THEN
        CASE 
            WHEN TRUNC(MONTHS_BETWEEN(PPOS.ACTUAL_TERMINATION_DATE, PPOS.DATE_START) / 12) > 0 
            THEN TRUNC(MONTHS_BETWEEN(PPOS.ACTUAL_TERMINATION_DATE, PPOS.DATE_START) / 12) || ' Years / '
        END ||
        CASE 
            WHEN TRUNC(MOD(MONTHS_BETWEEN(PPOS.ACTUAL_TERMINATION_DATE, PPOS.DATE_START), 12)) > 0 
            THEN TRUNC(MOD(MONTHS_BETWEEN(PPOS.ACTUAL_TERMINATION_DATE, PPOS.DATE_START), 12)) || ' Months / '
        END ||
        CASE 
            WHEN TRUNC(PPOS.ACTUAL_TERMINATION_DATE - ADD_MONTHS(PPOS.DATE_START, TRUNC(MONTHS_BETWEEN(PPOS.ACTUAL_TERMINATION_DATE, PPOS.DATE_START)))) > 0
            THEN TRUNC(PPOS.ACTUAL_TERMINATION_DATE - ADD_MONTHS(PPOS.DATE_START, TRUNC(MONTHS_BETWEEN(PPOS.ACTUAL_TERMINATION_DATE, PPOS.DATE_START)))) || ' Days'
            END
        
    ELSE NULL
END TENURE,
  PACTL.CHECKLIST_DISPLAY_NAME     SURVEY_TYPE,
  HQV.QUESTION_TEXT                QUESTION_NAME,
CASE 
    WHEN HPRV.ANSWER_CLOB IS NOT NULL THEN TO_CHAR(HPRV.ANSWER_CLOB)
    WHEN HPRV.ANSWER_TEXT IS NOT NULL THEN HPRV.ANSWER_TEXT
    WHEN HQPRV.LONG_TEXT  IS NOT NULL THEN HQPRV.LONG_TEXT
    WHEN HPRV.ANSWER_LIST IS NOT NULL THEN
        ( SELECT LISTAGG(NVL(HQAV.LONG_TEXT,HQAV.SHORT_TEXT),', ') 
            WITHIN GROUP (ORDER BY HQAV.SEQ_NUM)
            FROM HRQ_QSTN_ANSWERS_VL HQAV
            WHERE HQAV.QUESTION_ID = HQV.QUESTION_ID
            AND INSTR(
                    ',' || REPLACE(HPRV.ANSWER_LIST,';',',') || ',',
                    ',' || TO_CHAR(HQAV.QSTN_ANSWER_ID) || ','
                ) > 0
        )
    ELSE NULL
END RESPONSE 

FROM PER_ALL_PEOPLE_F                           PAPF   
INNER JOIN PER_PERSON_NAMES_F                   PPNF         ON PPNF.PERSON_ID = PAPF.PERSON_ID
                                                            AND PPNF.NAME_TYPE = 'GLOBAL'
INNER JOIN PER_ALL_ASSIGNMENTS_M                PAAM         ON PAAM.PERSON_ID = PAPF.PERSON_ID
                                                            AND PAAM.EFFECTIVE_END_DATE = (
                                                                SELECT MAX(XPAAM.EFFECTIVE_END_DATE) 
                                                                FROM PER_ALL_ASSIGNMENTS_M XPAAM
                                                                WHERE XPAAM.ASSIGNMENT_ID = PAAM.ASSIGNMENT_ID
                                                                )
                                                            AND PAAM.PRIMARY_FLAG = 'Y'
                                                            AND PAAM.PRIMARY_ASSIGNMENT_FLAG = 'Y'
                                                            AND PAAM.ASSIGNMENT_TYPE = 'E'
INNER JOIN PER_JOBS_F_TL                        PJFT         ON PJFT.JOB_ID = PAAM.JOB_ID
                                                            AND SYSDATE BETWEEN PJFT.EFFECTIVE_START_DATE AND PJFT.EFFECTIVE_END_DATE
                                                            AND PJFT.LANGUAGE = 'US'
INNER JOIN PER_ASSIGNMENT_SUPERVISORS_F         PASF         ON PASF.ASSIGNMENT_ID =PAAM.ASSIGNMENT_ID
                                                            AND PASF.MANAGER_TYPE = 'LINE_MANAGER'
INNER JOIN PER_ALL_PEOPLE_F                     MGR_PAPF     ON MGR_PAPF.PERSON_ID = PASF.MANAGER_ID
                                                            AND SYSDATE BETWEEN MGR_PAPF.EFFECTIVE_START_DATE AND MGR_PAPF.EFFECTIVE_END_DATE
INNER JOIN PER_PERSON_NAMES_F                   MGR_NAME     ON MGR_NAME.PERSON_ID = PASF.MANAGER_ID
                                                            AND SYSDATE BETWEEN MGR_NAME.EFFECTIVE_START_DATE AND MGR_NAME.EFFECTIVE_END_DATE
                                                            AND MGR_NAME.NAME_TYPE = 'GLOBAL'
INNER JOIN PER_PERIODS_OF_SERVICE               PPOS         ON PPOS.PERSON_ID = PAPF.PERSON_ID 
                                                            AND PPOS.PRIMARY_FLAG = 'Y'
                                                            AND PPOS.ACTUAL_TERMINATION_DATE IS NOT NULL
INNER JOIN PER_DEPARTMENTS                      PD           ON PD.ORGANIZATION_ID = PAAM.ORGANIZATION_ID
LEFT OUTER JOIN PER_ACTION_OCCURRENCES          PAO          ON PAO.ACTION_OCCURRENCE_ID = PPOS.ACTION_OCCURRENCE_ID
LEFT OUTER JOIN HR_LOCATIONS                    HRL          ON HRL.LOCATION_ID = PAAM.LOCATION_ID
                                                            AND SYSDATE BETWEEN HRL.EFFECTIVE_START_DATE AND HRL.EFFECTIVE_END_DATE
LEFT OUTER JOIN PER_ALLOCATED_CHECKLISTS        PAC          ON PAPF.PERSON_ID = PAC.PERSON_ID 
LEFT OUTER JOIN PER_ALLOCATED_CHECKLISTS_TL     PACTL        ON PACTL.ALLOCATED_CHECKLIST_ID = PAC.ALLOCATED_CHECKLIST_ID 
                                                            AND PACTL.LANGUAGE = 'US'
LEFT OUTER JOIN PER_ALLOCATED_TASKS             PAT          ON PAT.ALLOCATED_CHECKLIST_ID = PAC.ALLOCATED_CHECKLIST_ID
LEFT OUTER JOIN PER_ACTION_REASONS_TL           PART         ON PART.ACTION_REASON_ID = PAO.ACTION_REASON_ID
                                                            AND PART.LANGUAGE = 'US'
LEFT OUTER JOIN PER_ACTIONS_TL                  PATL         ON PATL.ACTION_ID = PAO.ACTION_ID
                                                            AND PATL.LANGUAGE = 'US'
LEFT OUTER JOIN HRQ_QUESTIONNAIRES_B            HQB          ON HQB.QUESTIONNAIRE_ID = PAT.QUESTIONNAIRE_ID 
LEFT OUTER JOIN HRQ_QSTNR_ALL_QSTNS_V           HQAQV        ON HQAQV.QUESTIONNAIRE_ID = PAT.QUESTIONNAIRE_ID
                                                            AND HQAQV.QUESTIONNAIRE_ID = HQB.QUESTIONNAIRE_ID
LEFT OUTER JOIN HRQ_QUESTIONS_VL                HQV          ON HQV.QUESTION_ID = HQAQV.QUESTION_ID
LEFT OUTER JOIN HRQ_QSTNR_PCPT_RESPONSES_V      HQPRV        ON HQPRV.QUESTION_ID = HQAQV.QUESTION_ID
                                                            AND HQPRV.PARTICIPANT_ID = PAT.DOCUMENT_ENTITY_ID
LEFT OUTER JOIN HRQ_PTCPNT_RESPONSES_V          HPRV         ON HPRV.QUESTIONNAIRE_ID = HQB.QUESTIONNAIRE_ID
                                                            AND HPRV.PARTICIPANT_ID = PAT.DOCUMENT_ENTITY_ID
                                                            AND HPRV.QSTNR_QUESTION_ID = HQAQV.QSTNR_QUESTION_ID 
WHERE 1=1
AND PAPF.PERSON_NUMBER = NVL(:P_EMPLOYEE_ID ,PAPF.PERSON_NUMBER)
AND NVL(PACTL.CHECKLIST_DISPLAY_NAME, 'X') = NVL(:P_SURVEY_TYPE, NVL(PACTL.CHECKLIST_DISPLAY_NAME, 'X'))
AND HQV.QUESTION_TEXT IS NOT NULL
AND LOWER(PACTL.CHECKLIST_DISPLAY_NAME) LIKE '%exit%interview%-%'