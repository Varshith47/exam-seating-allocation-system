def normalize_roll_number(value):
    if value is None: return ""
    s=str(value).strip()
    if s.lower() in {"nan","none","null"}: return ""
    if s.endswith(".0"): s=s[:-2]
    return s.upper()

def allocate_seats(students, halls):
    assigned=[]; i=0
    for hall in halls:
        for row in range(1,int(hall["rows_count"])+1):
            for col in range(1,int(hall["cols_count"])+1):
                if i >= len(students): return assigned, []
                s=students[i]
                assigned.append({"roll_number":s["roll_number"],"full_name":s.get("full_name",""),"hall_name":hall["hall_name"],"seat_number":f"R{row}-C{col}","row_number":row,"col_number":col})
                i+=1
    return assigned, students[i:]
