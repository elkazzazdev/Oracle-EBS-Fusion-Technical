CREATE OR REPLACE VIEW MK_ALL_EMPLOYEE_INFO_V AS


    SELECT 
        FU.USER_ID,
        FU.USER_NAME,
        PAPF.PERSON_ID        AS EMPLOYEE_ID,
        PAPF.EMPLOYEE_NUMBER,
        PAPF.FULL_NAME ,
        PAPF.NATIONALITY ,
        PAPF.SEX   GENDER ,
        PAP.POSITION_ID ,
        PAP.NAME ,
        PAP.ORGANIZATION_ID ,
        HAOU.NAME ORG_NAME, 
        PAPAY.PAYROLL_ID ,
        PAPAY.PAYROLL_NAME ,
        PPP.PAY_PROPOSAL_ID ,
        PPB.NAME PAY_BASIS_NAME ,
        PPP.PROPOSED_SALARY_N BASIC_SALARY ,
        PPP.PROPOSAL_REASON,
        PPP.CHANGE_DATE  SALARY_CHANGE_DATE,
        PASF.EFFECTIVE_START_DATE , 
        PASF.EFFECTIVE_END_DATE ,
        --MAX  (PPP.PROPOSED_SALARY_N * 1.1) OVER (PARTITION BY PASF.ASSIGNMENT_ID) NEW_SALARY,
        MK_ALL_EMPLOYEE_INFO_PK.MK_GET_MAX_SALARY_FN   (PAPF.PERSON_ID) MAX_SALARY ,
        MK_ALL_EMPLOYEE_INFO_PK.MK_GET_COUNT_RECORD_FN (FU.USER_ID) RECORD_COUNT
        
    FROM       PER_ALL_PEOPLE_F                     PAPF

    INNER JOIN FND_USER                             FU           ON FU.EMPLOYEE_ID = PAPF.PERSON_ID

    INNER JOIN PER_ALL_POSITIONS                    PAP          ON PAP.BUSINESS_GROUP_ID =  PAPF.BUSINESS_GROUP_ID
                                                                AND PAP.DATE_EFFECTIVE =  PAPF.EFFECTIVE_END_DATE
                                                                    
    INNER JOIN PAY_ALL_PAYROLLS_F                   PAPAY        ON PAPAY.BUSINESS_GROUP_ID = PAPF.BUSINESS_GROUP_ID     

    INNER JOIN HR_ALL_ORGANIZATION_UNITS            HAOU         ON HAOU.ORGANIZATION_ID = PAP.ORGANIZATION_ID       
                
    LEFT OUTER JOIN PER_ALL_ASSIGNMENTS_F           PASF         ON PASF.PERSON_ID = PASF.PERSON_ID
                                                                AND TRUNC(SYSDATE) BETWEEN PASF.EFFECTIVE_START_DATE AND PASF.EFFECTIVE_END_DATE
                                                                
    LEFT OUTER JOIN PER_PAY_PROPOSALS               PPP          ON PPP.ASSIGNMENT_ID = PASF.ASSIGNMENT_ID   
                                                                AND PPP.APPROVED = 'Y'
    LEFT OUTER JOIN PER_PAY_BASES                   PPB          ON PASF.PAY_BASIS_ID = PPB.PAY_BASIS_ID 

                                                                
                                                                
    WHERE 1=1 
    AND PASF.PRIMARY_FLAG = 'Y'
    AND PPP.CHANGE_DATE <= TRUNC(SYSDATE)
    --AND PAPF.PERSON_ID = :P_PERSON_ID   
      
    --PAPF.PERSON_ID > 3840                                                    
    --FU.USER_ID        > 1001232

