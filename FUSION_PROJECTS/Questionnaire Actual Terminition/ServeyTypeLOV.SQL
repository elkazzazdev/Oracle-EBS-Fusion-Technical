SELECT DISTINCT
      PACTL.CHECKLIST_DISPLAY_NAME   SURVEY_TYPE 
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
                                                            AND PAAM.ASSIGNMENT_TYPE = 'E'
INNER JOIN PER_PERIODS_OF_SERVICE               PPOS         ON PPOS.PERSON_ID = PAPF.PERSON_ID 
                                                            AND PPOS.PRIMARY_FLAG = 'Y'
                                                            AND PPOS.ACTUAL_TERMINATION_DATE IS NOT NULL
INNER JOIN PER_ASSIGNMENT_STATUS_TYPES          PAST         ON PAST.ASSIGNMENT_STATUS_TYPE_ID = PAAM.ASSIGNMENT_STATUS_TYPE_ID 
INNER JOIN PER_DEPARTMENTS                      PD           ON PD.ORGANIZATION_ID = PAAM.ORGANIZATION_ID
INNER JOIN PER_ACTION_OCCURRENCES               PAO          ON PAO.ACTION_OCCURRENCE_ID = PPOS.ACTION_OCCURRENCE_ID
LEFT OUTER JOIN PER_ALLOCATED_CHECKLISTS        PAC          ON PAPF.PERSON_ID = PAC.PERSON_ID 
LEFT OUTER JOIN PER_ALLOCATED_CHECKLISTS_TL     PACTL        ON PACTL.ALLOCATED_CHECKLIST_ID = PAC.ALLOCATED_CHECKLIST_ID 
                                                            AND PACTL.LANGUAGE = 'US'
                                                            

WHERE 1=1
AND LOWER(PACTL.CHECKLIST_DISPLAY_NAME) LIKE '%exit%interview%-%'