declare 
y varchar2(4); y2 varchar2(4);
begin
y:=to_char(sysdate,'yyyy');
if to_char(sysdate,'mm')<='08'
  then y:=y-1;
end if;
select to_char(max(megrendeles_datuma),'yyyy') into y2 from s_megrendeles;
y:=y-y2;

update s_megrendeles
set megrendeles_datuma=add_months(megrendeles_datuma, 12*y);

update s_ugyfel
set szul_dat=add_months(szul_dat, 12*y);

update s_ut
set indulasi_ido=add_months(indulasi_ido, 12*y),
erkezesi_ido=add_months(erkezesi_ido, 12*y);
commit;
end;

