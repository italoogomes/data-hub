/* Atualizar custo dos itens nas vendas, para itens com custo zero e Notas  */

SELECT
    C.CodEmp       as "Emp",
    C.NuNota       as "Controle",
    C.DtNeg        as "Data",
    I.CODPROD      as "Produto",
   
    I.QTDNEG       as "Qtde",
    round((I.VLRTOT / I.QTDNEG),2)  as "VlUnit",
    I.VLRTOT       as "VlTotal",
    Nvl(I.Ad_VlrCustoIara,0)             as "CustoUnit",
    Nvl(I.Ad_VlrCustoIara * I.QTDNEG ,0) as "CustoTotal",
     
    (select TC.CusRep
     from TgfCus TC
     where TC.CodEmp = C.CodEmp
       and TC.CodProd = I.CodProd
       and TC.DtAtual <= C.DtNeg
     order by DtAtual desc
     FETCH FIRST 1 ROWS ONLY) as "CustoLista",
    
    (select round(VD.Diferencial,2)      
     from V_DadosProduto_MMA VD
     where VD.CodEmp = C.CodEmp
     and VD.CodProd = I.CodProd
     and VD.CodTipOper = 1101
     and VD.CodParc = C.CodParc
     FETCH FIRST 1 ROWS ONLY) as "AdCusto",
     
     round(((select TC.CusRep
       from TgfCus TC
       where TC.CodEmp = C.CodEmp
         and TC.CodProd = I.CodProd
         and TC.DtAtual <= C.DtNeg
       order by DtAtual desc
       FETCH FIRST 1 ROWS ONLY)
      * (1 + ((select round(VD.Diferencial,2)      
               from V_DadosProduto_MMA VD
               where VD.CodEmp = C.CodEmp
                 and VD.CodProd = I.CodProd
                 and VD.CodTipOper = 1101
                 and VD.CodParc = C.CodParc
                FETCH FIRST 1 ROWS ONLY) / 100))),2) as "CustoNovo"
       
FROM TGFCAB C
  JOIN TGFITE I ON I.NUNOTA = C.NUNOTA
  JOIN TGFTOP T ON T.CODTIPOPER = C.CODTIPOPER 
               AND T.DHALTER = C.DHTIPOPER
         
WHERE C.TIPMOV IN ('V','D')    -- Vendas e Pedidos
  and C.STATUSNOTA = 'L'   -- Confirmado
  and T.GolSinal = '-1'    -- Feito no Sankhya
  and C.DtNeg between '01/02/26' and '12/02/26'
  and Nvl(I.Ad_VlrCustoIara,0) = 0
  and Nvl((select TC.CusRep
           from TgfCus TC
           where TC.CodEmp = C.CodEmp
             and TC.CodProd = I.CodProd
             and TC.DtAtual <= C.DtNeg
           order by DtAtual desc
           FETCH FIRST 1 ROWS ONLY),0) <> 0
/*
and exists (select 1
              from AD_CustoProdComissao_MMA CT
              where CT.NuNota = I.NuNota
                and CT.Prod = I.CodProd)
*/
ORDER BY C.DtNeg, C.NuNota


/* Inserir Produtos na Lista para serem atualizados


INSERT INTO AD_CustoProdComissao_MMA (NUNOTA, PROD, CUSTO)
SELECT
    C.NuNota,
    I.CODPROD,
    round(((select TC.CusRep
       from TgfCus TC
       where TC.CodEmp = C.CodEmp
         and TC.CodProd = I.CodProd
         and TC.DtAtual <= C.DtNeg
       order by DtAtual desc
       FETCH FIRST 1 ROWS ONLY)
      * (1 + ((select round(VD.Diferencial,2)      
               from V_DadosProduto_MMA VD
               where VD.CodEmp = C.CodEmp
                 and VD.CodProd = I.CodProd
                 and VD.CodTipOper = 1101
                 and VD.CodParc = C.CodParc
                FETCH FIRST 1 ROWS ONLY) / 100))),2) 
       
FROM TGFCAB C
  JOIN TGFITE I ON I.NUNOTA = C.NUNOTA
  JOIN TGFTOP T ON T.CODTIPOPER = C.CODTIPOPER 
               AND T.DHALTER = C.DHTIPOPER
         
WHERE C.TIPMOV IN ('V','D')    -- Vendas e Pedidos
  and C.STATUSNOTA = 'L'   -- Confirmado
  and T.GolSinal = '-1'    -- Feito no Sankhya
  and C.DtNeg between '01/02/26' and '12/02/26'
  and Nvl(I.Ad_VlrCustoIara,0) = 0
  and Nvl((select TC.CusRep
           from TgfCus TC
           where TC.CodEmp = C.CodEmp
             and TC.CodProd = I.CodProd
             and TC.DtAtual <= C.DtNeg
           order by DtAtual desc
           FETCH FIRST 1 ROWS ONLY),0) <> 0
ORDER BY C.NuNota, I.CODPROD

*/


/*

update TGFITE I
  set I.Ad_VlrCustoIara = (select CT.Custo
                           from AD_CustoProdComissao_MMA CT
                           where CT.NuNota = I.NuNota
                             and CT.Prod = I.CodProd
                           FETCH FIRST 1 ROWS ONLY)
where Nvl(I.Ad_VlrCustoIara,0) = 0
  and exists(select C.NuNota
             from TGFCAB C
               JOIN TGFTOP T ON T.CODTIPOPER = C.CODTIPOPER 
                            AND T.DHALTER = C.DHTIPOPER
             WHERE C.NUNOTA = I.NUNOTA 
               and C.TIPMOV IN ('V','D')    -- Vendas e Pedidos
               and C.STATUSNOTA = 'L'   -- Confirmado
               and T.GolSinal = '-1'    -- Feito no Sankhya
               and C.DtNeg between '01/02/26' and '12/02/26')
               
  and exists (select 1
              from AD_CustoProdComissao_MMA CT
              where CT.NuNota = I.NuNota
                and CT.Prod = I.CodProd)
                
    */
