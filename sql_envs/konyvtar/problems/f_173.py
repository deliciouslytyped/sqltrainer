class Check(Checker):
    def check_state(self):
        #TODO technically incorrect, the spec says NUMBER(5) but for getting the check to work there is an implicit precision = 0
        #TODO not sure why, VARCHAR2(30) ends up as VARCHAR(30), same for varchar2(40)
        #DATE() instead of DATE for some reason
        return self.table_exists("szemely") and \
            self.table_column("szemely", "azon", "NUMBER(5,0)") and \
            self.table_column("szemely", "nev", "VARCHAR(30)", "C", "not null") and \
            self.table_column("szemely", "szul_dat", "DATE()") and \
            self.table_column("szemely", "irsz", "CHAR(4)") and \
            self.table_column("szemely", "cim", "VARCHAR(40)") and \
            self.table_column("szemely", "zsebpenz", "NUMBER(12,2)") and \
            self.primary_key("szemely", ("azon",)) and \
            self.unique_key("szemely", ("nev", "szul_dat", "cim")) and \
            self.check_constraint("szemely", "zsebpenz > 100")