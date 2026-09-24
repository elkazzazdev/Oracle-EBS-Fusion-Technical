SELECT 
  'Exit_Interview_Template'   TEMPLATE,
  'en-US'                     LOCALE,
  'HTML'                      OUTPUT_FORMAT,
  'EMAIL'                     DELIVER_MEDIA,
  'elkazzaz.dev@gmail.com'    PARAMETER1,
  null                        PARAMETER2,
  'no-reply@company.com'      PARAMETER3,
  'Exit Interview Checklist Completion Notice - ' || FULL_NAME   PARAMETER4,

 '&lt;p&gt;Hello&lt;/p&gt;'   PARAMETER5,

  'true'  PARAMETER6  
FROM (
 SELECT DISTINCT
  PAPF.PERSON_NUMBER                                 EMPLOYEE_ID, 
  PPNF.DISPLAY_NAME                                  FULL_NAME,
  HAPFT.NAME                                         JOB_TITLE,
  MGR_NAME.DISPLAY_NAME                              MANAGER_NAME,
  PD.NAME                                            DEPARTMENT, 
  TO_CHAR(PPOS.DATE_START,'DD-MM-YYYY')              HIRE_DATE ,
  TO_CHAR(PPOS.ACTUAL_TERMINATION_DATE,'DD-MM-YYYY') LAST_WORKING_DATE,
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
  PACTL.CHECKLIST_DISPLAY_NAME                       SURVEY_TYPE
FROM PER_ALL_PEOPLE_F                            PAPF   
INNER JOIN PER_PERSON_NAMES_F                    PPNF         ON PPNF.PERSON_ID = PAPF.PERSON_ID
                                                             AND PPNF.NAME_TYPE = 'GLOBAL'
INNER JOIN PER_ALL_ASSIGNMENTS_M                 PAAM         ON PAAM.PERSON_ID = PAPF.PERSON_ID
                                                             AND PAAM.EFFECTIVE_END_DATE = (
                                                                 SELECT MAX(XPAAM.EFFECTIVE_END_DATE) 
                                                                 FROM PER_ALL_ASSIGNMENTS_M XPAAM
                                                                 WHERE XPAAM.ASSIGNMENT_ID = PAAM.ASSIGNMENT_ID
                                                                 )
                                                             AND PAAM.PRIMARY_FLAG = 'Y'
                                                             AND PAAM.PRIMARY_ASSIGNMENT_FLAG = 'Y'
                                                             AND PAAM.ASSIGNMENT_TYPE = 'E'
INNER JOIN HR_ALL_POSITIONS_F_TL                 HAPFT        ON HAPFT.POSITION_ID = PAAM.POSITION_ID
                                                             AND SYSDATE BETWEEN HAPFT.EFFECTIVE_START_DATE AND HAPFT.EFFECTIVE_END_DATE
                                                             AND HAPFT.LANGUAGE = 'US'
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

WHERE 1=1
AND LOWER(PACTL.CHECKLIST_DISPLAY_NAME) LIKE '%exit%interview%-%'
AND PAC.CHECKLIST_STATUS = 'COM'
)