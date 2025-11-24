DELETE FROM users WHERE email='ysr@gmail.com';

INSERT INTO users (email, password_hash, role, full_name)
VALUES ('ysr@gmail.com', '$bcrypt-sha256$v=2,t=2b,r=12$F/Cu.jD99Iv/o2d.bQYZeu$1FKDsEFGwn5OffuC5Opkq3joMm2Gwha', 'admin', 'Yasir Admin');
