def validate_tc_no(tc_no: str) -> bool:
    if not tc_no or not isinstance(tc_no, str):
        return False
    
    if not tc_no.isdigit() or len(tc_no) != 11:
        return False
    
    if tc_no[0] == '0':
        return False
    
    digits = [int(d) for d in tc_no]
    
    sum_odd = sum(digits[i] for i in range(0, 9, 2))
    sum_even = sum(digits[i] for i in range(1, 8, 2))
    
    check1 = (sum_odd * 7 - sum_even) % 10
    if check1 != digits[9]:
        return False
    
    check2 = (sum_odd + sum_even + digits[9]) % 10
    if check2 != digits[10]:
        return False
    
    return True

def validate_tax_number(tax_no: str) -> bool:
    if not tax_no or not isinstance(tax_no, str):
        return False
    
    if not tax_no.isdigit() or len(tax_no) != 10:
        return False
    
    if tax_no[0] == '0':
        return False
    
    digits = [int(d) for d in tax_no]
    
    sum_all = sum(digits[:9])
    check = sum_all % 10
    
    return check == digits[9]

