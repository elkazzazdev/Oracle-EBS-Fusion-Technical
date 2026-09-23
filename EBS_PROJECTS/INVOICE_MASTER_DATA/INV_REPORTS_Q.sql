SELECT 
    RCTA.CUSTOMER_TRX_ID, --- PRIMARY KEY
    RCTA.TRX_NUMBER                       INVOICE_NUMBER ,
    RCTA.INTERFACE_HEADER_ATTRIBUTE1      REFERANCE ,
    RCTA.CUST_TRX_TYPE_ID,
    RCTA.BILL_TO_CONTACT_ID,
    RCTA.BATCH_SOURCE_ID, --- RA_BATCH_SOURCES_ALL , CUST_TRX_TYPE_ID
    RCTA.BILL_TO_CUSTOMER_ID,
    RCTA.BILL_TO_SITE_USE_ID ,
    RCTA.INVOICE_CURRENCY_CODE             CURRENCY,
    RCTA.COMPLETE_FLAG,   ---- IMPORTANT
    RCTA.PAYING_CUSTOMER_ID,
    RCTA.STATUS_TRX,
    RCTA.TRX_DATE INVOICE_DATE ,
    RCTA.SET_OF_BOOKS_ID , 
    
    HP.PARTY_NUMBER                        CUSTOMER_NUMBER ,
    HP.PARTY_NAME                          CUSTOMER_NAME,
    HP.ADDRESS1                            CUSTOMER_ADDRESS ,
    HP.COUNTRY , 
    HP.STATUS ,     
    
    RCTL.LINE_NUMBER ,
    RCTL.LINE_TYPE , 
    RCTL.DESCRIPTION , 
    RCTL.UNIT_SELLING_PRICE                UNIT_PRICE,
    RCTL.EXTENDED_AMOUNT                   E_AMOUNT,
    RCTL.QUANTITY_INVOICED, 
    
    RBSA.NAME                              SOURCE_NAME ,
    
    RTT.TERM_ID TERM_ID,
    RTT.NAME                               TRM_NAME, 
    
    ARM.NAME                               RECEPIT_NAME,
    ARM.RECEIPT_METHOD_ID RECEPIT_ID,
    ARM.PAYMENT_CHANNEL_CODE ,
    
    RCTTA.NAME                             TYPE_NAME,
    
    ARC.NAME                               CLASS_NAME, 
    
    GL.NAME                                GL_NAME
    
FROM RA_CUSTOMER_TRX_ALL                                RCTA    -- MAIN TABELS

INNER JOIN RA_CUST_TRX_TYPES_ALL                        RCTTA   ON RCTTA.CUST_TRX_TYPE_ID = RCTA.CUST_TRX_TYPE_ID  
                                                               AND RCTTA.ORG_ID = RCTA.ORG_ID
                                                                        
INNER JOIN GL_LEDGERS                                   GL      ON GL.LEDGER_ID = RCTA.SET_OF_BOOKS_ID

LEFT OUTER JOIN RA_CUSTOMER_TRX_LINES_ALL               RCTL    ON RCTL.CUSTOMER_TRX_ID = RCTA.CUSTOMER_TRX_ID 
                                                                        
LEFT OUTER JOIN HZ_CUST_ACCOUNTS                        HCA     ON RCTA.BILL_TO_CUSTOMER_ID = HCA.CUST_ACCOUNT_ID

LEFT OUTER JOIN HZ_PARTIES                              HP      ON HP.PARTY_ID = HCA.PARTY_ID 

LEFT OUTER JOIN AR_RECEIPT_METHODS                      ARM     ON ARM.RECEIPT_METHOD_ID = RCTA.RECEIPT_METHOD_ID

LEFT OUTER JOIN RA_TERMS_TL                             RTT     ON RTT.TERM_ID = RCTA.TERM_ID   
                                                               AND RTT.LANGUAGE = RTT.LANGUAGE 
                                                                    
LEFT OUTER JOIN AR_RECEIPT_CLASSES                      ARC     ON ARC.RECEIPT_CLASS_ID = ARM.RECEIPT_CLASS_ID
                                                 
LEFT OUTER JOIN RA_BATCH_SOURCES_ALL                    RBSA    ON RBSA.BATCH_SOURCE_ID =  RCTA.BATCH_SOURCE_ID    
                                                               AND RBSA.ORG_ID = RCTA.ORG_ID
                                                                                           
WHERE 1=1 
AND RCTA.COMPLETE_FLAG   = 'Y'
AND RCTL.LINE_TYPE       = 'LINE'
AND RCTA.TRX_NUMBER = '10033396'
-- AND RCTA.TRX_NUMBER = NVL(:P_INVOICE_NUMBER , RCTA.TRX_NUMBER)
;