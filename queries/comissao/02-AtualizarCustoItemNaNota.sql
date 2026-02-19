
select 

  C.NuNota,
  C.AD_VlrCustoIara,
  C.AD_VlrBaseComInt,
  C.AD_PMV,
  C.AD_Margem,
  C.AD_AliqComInt,
  C.AD_VlrComInt, 
  
  Nvl((select TC.PercComissao
       from AD_TABCOMISSAO_MMA TC
       where TC.Margem <= C.AD_Margem
         and TC.PrazoMedio <= C.AD_PMV
       order by TC.Margem desc, TC.PrazoMedio Desc
       FETCH FIRST 1 ROW ONLY),0) as "AliqCalc",
  (select Nvl(TV.AD_TaxaVendaMMA, 0)
   from TgfTpv TV 
   where TV.CodTipVenda = C.CodTipVenda
     and TV.DHAlter = (Select max(TV2.DHAlter)
                       from TgfTpv TV2
                       where TV2.CodTipVenda = TV.CodTipVenda)) as "Taxa",
  
  round(C.Ad_VlrBaseComInt / (1 + (((select Nvl(TV.AD_TaxaVendaMMA, 0)
                                     from TgfTpv TV 
                                     where TV.CodTipVenda = C.CodTipVenda
                                       and TV.DHAlter = (Select max(TV2.DHAlter)
                                                         from TgfTpv TV2
                                                          where TV2.CodTipVenda = TV.CodTipVenda))/100) * -1)),2) as "NovaBase",
  
  C.TotalCustoProd as "CustoS",
  C.VlrNota        as "VendaS",
  C.*
  
from TGFCAB C
where C.TIPMOV IN ('V','D')    -- Vendas e Pedidos e Devolucao
  and C.STATUSNOTA = 'L'   -- Confirmado
  and C.DtNeg between '01/02/26' and '12/02/26'
 -- and C.NuNota = 1170422

  and exists (select 1
              from TGFTOP T 
              where T.CODTIPOPER = C.CODTIPOPER 
                and T.DHALTER = C.DHTIPOPER
                and T.GolSinal = '-1')
  -- and C.AD_PMV is null
 /*  and (select Nvl(TV.AD_TaxaVendaMMA, 0)
   from TgfTpv TV 
   where TV.CodTipVenda = C.CodTipVenda
     and TV.DHAlter = (Select max(TV2.DHAlter)
                       from TgfTpv TV2
                       where TV2.CodTipVenda = TV.CodTipVenda)) < 0 */
   /*                    
    and (exists (select 1
               from TgfTpv TV 
               where TV.CodTipVenda = C.CodTipVenda
                 and TV.DHAlter = (Select max(TV2.DHAlter)
                                   from TgfTpv TV2
                                   where TV2.CodTipVenda = TV.CodTipVenda)
                 and Nvl(TV.AD_TaxaVendaMMA, 0) < 0
                 --and not REGEXP_LIKE(TV.DescrTipVenda, 'P(10|[1-9])$') 
                 and (TV.DescrTipVenda like ('%CARTAO%') or TV.DescrTipVenda like ('%CARTÃO%')))
      or  Nvl(C.Ad_PMV,0) < 0)
  */

/* Atualizar o custo acumulado dos itens na nota fiscal

update TGFCAB C
  set C.Ad_VlrCustoIara = (select round(sum(I.Ad_VlrCustoIara * I.QTDNEG),2)
                           from TGFITE I 
                           where I.NUNOTA = C.NUNOTA)
where C.TIPMOV IN ('V','D')    -- Vendas e Pedidos
  and C.STATUSNOTA = 'L'   -- Confirmado
  and C.DtNeg between '01/02/26' and '12/02/26'
  and exists (select 1
              from TGFTOP T 
              where T.CODTIPOPER = C.CODTIPOPER 
                and T.DHALTER = C.DHTIPOPER
                and T.GolSinal = '-1')
                
*/


/* Atualizar o prazo medio

update TGFCAB C
  set C.Ad_PMV = Nvl(round((select sum((TF.DtVenc - TF.DtNeg) * TF.VlrDesdob) / sum(TF.VlrDesdob)
                            from TgfFin TF
                            where TF.CodEmp = C.CodEmp
                             and TF.NuNota = C.NuNota),2),0)
where C.TIPMOV IN ('V','D')    -- Vendas e Pedidos
  and C.STATUSNOTA = 'L'   -- Confirmado
  and C.DtNeg between '01/02/26' and '12/02/26'
  and exists (select 1
              from TGFTOP T 
              where T.CODTIPOPER = C.CODTIPOPER 
                and T.DHALTER = C.DHTIPOPER
                and T.GolSinal = '-1')
                
*/

/* Atualiza o prazo médio para zero para condição de pagamento cartao ou prazo negativo
  
update TGFCAB C
  set C.Ad_PMV = 0
where C.TIPMOV IN ('V','D')    -- Vendas e Pedidos
  and C.STATUSNOTA = 'L'   -- Confirmado
  and C.DtNeg between '01/02/26' and '12/02/26'
  and Nvl(C.Ad_PMV,0) <> 0
  and exists (select 1
              from TGFTOP T 
              where T.CODTIPOPER = C.CODTIPOPER 
                and T.DHALTER = C.DHTIPOPER
                and T.GolSinal = '-1')
  and (exists (select 1
               from TgfTpv TV 
               where TV.CodTipVenda = C.CodTipVenda
                 and TV.DHAlter = (Select max(TV2.DHAlter)
                                   from TgfTpv TV2
                                   where TV2.CodTipVenda = TV.CodTipVenda)
                 and Nvl(TV.AD_TaxaVendaMMA, 0) < 0
                 --and not REGEXP_LIKE(TV.DescrTipVenda, 'P(10|[1-9])$') 
                 and (TV.DescrTipVenda like ('%CARTAO%') or TV.DescrTipVenda like ('%CARTÃO%')))
      or  Nvl(C.Ad_PMV,0) < 0)
                
*/
  

/* Atualizar o valor base de comissao

update TGFCAB C
  set C.Ad_VlrBaseComInt = (select round(sum(I.VLRTOT),2)
                            from TGFITE I 
                            where I.NUNOTA = C.NUNOTA)
where C.TIPMOV IN ('V','D')    -- Vendas e Pedidos
  and C.STATUSNOTA = 'L'   -- Confirmado
  and C.DtNeg between '01/02/26' and '12/02/26'
  and exists (select 1
              from TGFTOP T 
              where T.CODTIPOPER = C.CODTIPOPER 
                and T.DHALTER = C.DHTIPOPER
                and T.GolSinal = '-1')
                
*/

/* Reduzir a taxa financeira da venda

update TGFCAB C
  set C.Ad_VlrBaseComInt = round(C.Ad_VlrBaseComInt 
                           / (1 + (((select Nvl(TV.AD_TaxaVendaMMA, 0)
                                     from TgfTpv TV 
                                     where TV.CodTipVenda = C.CodTipVenda
                                       and TV.DHAlter = (Select max(TV2.DHAlter)
                                                         from TgfTpv TV2
                                                         where TV2.CodTipVenda = TV.CodTipVenda))/100) * -1)),2)
  
where C.TIPMOV IN ('V','D')    -- Vendas e Pedidos
  and C.STATUSNOTA = 'L'   -- Confirmado
  and C.DtNeg between '01/02/26' and '12/02/26'
  and exists (select 1
              from TGFTOP T 
              where T.CODTIPOPER = C.CODTIPOPER 
                and T.DHALTER = C.DHTIPOPER
                and T.GolSinal = '-1')
  and (select Nvl(TV.AD_TaxaVendaMMA, 0)
       from TgfTpv TV 
       where TV.CodTipVenda = C.CodTipVenda
         and TV.DHAlter = (Select max(TV2.DHAlter)
                           from TgfTpv TV2
                           where TV2.CodTipVenda = TV.CodTipVenda)) < 0     
                           
*/
    
/*  Calcular a Margem

update TGFCAB C
  set C.Ad_Margem = round((1-(C.AD_VlrCustoIara / C.AD_VlrBaseComInt)) * 100,2)
where C.TIPMOV IN ('V','D')    -- Vendas e Pedidos
  and C.STATUSNOTA = 'L'   -- Confirmado
  and C.DtNeg between '01/02/26' and '12/02/26'
  and exists (select 1
              from TGFTOP T 
              where T.CODTIPOPER = C.CODTIPOPER 
                and T.DHALTER = C.DHTIPOPER
                and T.GolSinal = '-1')
                
*/

/*  Calcula Aliq Com

update TGFCAB C
  set C.Ad_AliqComInt = Nvl((select TC.PercComissao
                             from AD_TABCOMISSAO_MMA TC
                             where TC.Margem <= C.AD_Margem
                               and TC.PrazoMedio <= C.AD_PMV
                            order by TC.Margem desc, TC.PrazoMedio Desc
                            FETCH FIRST 1 ROW ONLY),0)
where C.TIPMOV IN ('V','D')    -- Vendas e Pedidos
  and C.STATUSNOTA = 'L'   -- Confirmado
  and C.DtNeg between '01/02/26' and '12/02/26'
  and exists (select 1
              from TGFTOP T 
              where T.CODTIPOPER = C.CODTIPOPER 
                and T.DHALTER = C.DHTIPOPER
                and T.GolSinal = '-1')

*/

/* Atualizar o valor da comissao

update TGFCAB C
  set C.AD_VlrComInt = round((C.AD_VlrBaseComInt * (C.AD_AliqComInt / 100)),2)
where C.TIPMOV IN ('V','D')    -- Vendas e Pedidos
  and C.STATUSNOTA = 'L'   -- Confirmado
  and C.DtNeg between '01/02/26' and '12/02/26'
  and exists (select 1
              from TGFTOP T 
              where T.CODTIPOPER = C.CODTIPOPER 
                and T.DHALTER = C.DHTIPOPER
                and T.GolSinal = '-1')
  
  */
                 
