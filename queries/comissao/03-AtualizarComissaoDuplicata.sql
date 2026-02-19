/* se necessario habilitar e desabilitar trigger 

alter trigger TRG_UPT_TGFFIN disable

alter trigger TRG_UPT_TGFFIN enable

select *
delete 
from AD_BASECOMDUPLICATA_MMA

*/


insert into AD_BASECOMDUPLICATA_MMA (NUNOTA, VALORBASEDUP, VALORCOM)
select 
 
  F.NuNota as "NUNOTA",
                 
  round(((select C.Ad_VlrBaseComInt
          from TgfCab C
            left join TGFTOP T on T.CODTIPOPER = C.CODTIPOPER 
                              and T.DHALTER = C.DHTIPOPER
           where C.TIPMOV IN ('V','D')    
             and C.NuNota = F.NuNota
             and C.STATUSNOTA = 'L'  
             and T.GolSinal = '-1') / (select Count(1)
                                       from TgfFin F2
                                       where F2.NuNota = F.NuNota)),2) as "VALORBASEDUP",
                         
  round(((select C.Ad_VlrComInt
          from TgfCab C
            left join TGFTOP T on T.CODTIPOPER = C.CODTIPOPER 
                              and T.DHALTER = C.DHTIPOPER
          where C.TIPMOV IN ('V','D')    
            and C.NuNota = F.NuNota
            and C.STATUSNOTA = 'L'  
            and T.GolSinal = '-1') / (select Count(1)
                                      from TgfFin F2
                                      where F2.NuNota = F.NuNota)),2) as "VALORCOMDUP"
from TGFFIN F
where 1 = 1
  and F.DtNeg >= '01/02/26'
  and F.Dtneg <= '12/02/26'
  and not F.NuNota is null
  and exists (select 1
              from TgfCab C
                left join TGFTOP T on T.CODTIPOPER = C.CODTIPOPER 
                                  and T.DHALTER = C.DHTIPOPER
              where C.TIPMOV IN ('V','D')    
                and C.NuNota = F.NuNota
                and C.STATUSNOTA = 'L'   
                and T.GolSinal = '-1') 
           
           
           
           
/* ACERTAR DE ACORDO COM OS DADOS APÓS SUBIR A TABELA ACIMA, QUANDO NECESSARIO HABILITAR E DESABILITAR TRIGGER     

            
update TGFFIN F
  set F.AD_VlrBaseComInt = (select F2.VALORBASEDUP
                            from AD_BASECOMDUPLICATA_MMA F2
                            where F2.NUNOTA = F.NUNOTA
                              AND ROWNUM = 1),
      F.AD_VlrComInt = (select F2.VALORCOM
                         from AD_BASECOMDUPLICATA_MMA F2
                         where F2.NUNOTA = F.NUNOTA
                           AND ROWNUM = 1)
where 1 = 1
  and F.DtNeg >= '01/02/26'
  and F.Dtneg <= '12/02/26'
  and not F.NuNota is null
 -- and not F.NuFin in (259550,259551, 259552, 259553)
  and exists (select 1
              from AD_BASECOMDUPLICATA_MMA F2
              where F2.NUNOTA = F.NUNOTA)
  and exists (select 1
              from TgfCab C
                left join TGFTOP T on T.CODTIPOPER = C.CODTIPOPER 
                                  and T.DHALTER = C.DHTIPOPER
              where C.TIPMOV IN ('V','D')    
                and C.NuNota = F.NuNota
                and C.STATUSNOTA = 'L'   
                and T.GolSinal = '-1') 
  
  */