SELECT DISTINCT
  PPNF.DISPLAY_NAME          FULL_NAME
FROM PER_ALL_PEOPLE_F                         PAPF   
INNER JOIN PER_PERSON_NAMES_F                 PPNF         ON PPNF.PERSON_ID = PAPF.PERSON_ID
                                                          AND PPNF.NAME_TYPE = 'GLOBAL'
INNER JOIN PER_ALL_ASSIGNMENTS_M              PAAM         ON PAAM.PERSON_ID = PAPF.PERSON_ID
                                                          AND PAAM.EFFECTIVE_END_DATE = (
                                                                  SELECT MAX(XPAAM.EFFECTIVE_END_DATE) 
                                                                  FROM PER_ALL_ASSIGNMENTS_M XPAAM
                                                                  WHERE XPAAM.ASSIGNMENT_ID = PAAM.ASSIGNMENT_ID
                                                              )
                                                          AND PAAM.PRIMARY_FLAG = 'Y'
                                                          AND PAAM.PRIMARY_ASSIGNMENT_FLAG = 'Y'
                                                          AND PAAM.ASSIGNMENT_TYPE = 'E'
INNER JOIN PER_PERIODS_OF_SERVICE             PPOS         ON PPOS.PERSON_ID = PAPF.PERSON_ID 
                                                          AND PPOS.PRIMARY_FLAG = 'Y'
                                                          AND PPOS.ACTUAL_TERMINATION_DATE IS NOT NULL
INNER JOIN PER_DEPARTMENTS                    PD           ON PD.ORGANIZATION_ID = PAAM.ORGANIZATION_ID
INNER JOIN PER_ACTION_OCCURRENCES             PAO          ON PAO.ACTION_OCCURRENCE_ID = PPOS.ACTION_OCCURRENCE_ID
LEFT OUTER JOIN HR_LOCATIONS                  HRL          ON HRL.LOCATION_ID = PAAM.LOCATION_ID
                                                          AND SYSDATE BETWEEN HRL.EFFECTIVE_START_DATE AND HRL.EFFECTIVE_END_DATE
LEFT OUTER JOIN PER_ALLOCATED_CHECKLISTS      PAC          ON PAPF.PERSON_ID = PAC.PERSON_ID 
LEFT OUTER JOIN PER_ALLOCATED_CHECKLISTS_TL   PACTL        ON PACTL.ALLOCATED_CHECKLIST_ID = PAC.ALLOCATED_CHECKLIST_ID 
                                                          AND PACTL.LANGUAGE = 'US'
                                                          AND LOWER(PACTL.CHECKLIST_DISPLAY_NAME) LIKE '%exit%interview%'
LEFT OUTER JOIN PER_ALLOCATED_TASKS           PAT          ON PAT.ALLOCATED_CHECKLIST_ID = PAC.ALLOCATED_CHECKLIST_ID
LEFT OUTER JOIN HRQ_QUESTIONNAIRES_TL         HQT          ON HQT.QUESTIONNAIRE_ID = PAT.QUESTIONNAIRE_ID 
                                                          AND HQT.LANGUAGE = 'US'
LEFT OUTER JOIN PER_ACTION_REASONS_TL         PART         ON PART.ACTION_REASON_ID = PAO.ACTION_REASON_ID
                                                          AND PART.LANGUAGE = 'US'
LEFT OUTER JOIN HRQ_QSTNR_ALL_QSTNS_V         HQAQV        ON HQAQV.QUESTIONNAIRE_ID = PAT.QUESTIONNAIRE_ID
LEFT OUTER JOIN HRQ_QUESTIONS_VL              HQV          ON HQV.QUESTION_ID = HQAQV.QUESTION_ID
LEFT OUTER JOIN HRQ_QSTNR_PCPT_RESPONSES_V    HQPRV        ON HQPRV.QUESTION_ID = HQAQV.QUESTION_ID
                                                          AND HQPRV.PARTICIPANT_ID = PAT.DOCUMENT_ENTITY_ID
LEFT OUTER JOIN HRQ_PTCPNT_RESPONSES_V        HPRV         ON HPRV.QSTNR_QUESTION_ID = HQAQV.QSTNR_QUESTION_ID
                                                          AND HPRV.PARTICIPANT_ID = PAT.DOCUMENT_ENTITY_ID
                                                          AND HPRV.QUESTIONNAIRE_ID = HQAQV.QUESTIONNAIRE_ID
WHERE 1=1
AND PACTL.CHECKLIST_DISPLAY_NAME = NVL(:P_SURVEY_TYPE,PACTL.CHECKLIST_DISPLAY_NAME)
AND HQV.QUESTION_TEXT IS NOT NULL
ORDER BY PPNF.DISPLAY_NAME