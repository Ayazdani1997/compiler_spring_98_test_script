import itertools
import os
import subprocess
import zipfile
from enum import Enum
from pandas import *

from shutil import *
import openpyxl

# HYPO: codes_folder and testcases_folder are available in file system

cur_dir = os.getcwd()
testcases_folder = os.path.join(cur_dir, "testcases")
project_dir = os.path.join(cur_dir, "../base_project")
runner_class = 'Toorla'
codes_folder = os.path.join(cur_dir, "codes")
FAILURE = "BUILD FAILURE"
testcase_extension = ".trl"
fail_prefix = "fail_"
pass_prefix = "pass_"
COMPILED = "Compiled"
excel_extension = ".xlsx"
output_extension = ".out"
separator = '_'
temp_directory = 'temp'
NUMOFSTUDENTS = 2
loss_rate = 0.2
RUNSNUM = "#run"
newer_version_sign = '$'
testcase_mapper_filename = "testcases.csv"
compressed_code_extension = ".zip"
files_to_copy = {'Toorla.g4': os.path.join(project_dir, 'grammar'),
                 'ToorlaCompiler.java': os.path.join(project_dir, 'src/')
    , 'TreePrinter.java': os.path.join(project_dir, 'src/toorla/visitor')}
pom_file = 'pom.xml'
max_run_num = 5
FULL_TESTCASE_GRADE = 1


class Grade(Enum):
    ERROR = -FULL_TESTCASE_GRADE
    FAULT = 0
    OK = FULL_TESTCASE_GRADE


def create_new_student(worksheet, sid_list):
    row = ([0 for i in range(worksheet.max_column)])
    for i in range(len(sid_list)):
        row[i] = sid_list[i]
    return row


def find_col_index_in_sheet(worksheet, col_name):
    if col_name is None:
        return -1
    for i in range(1, worksheet.max_column + 1):
        if worksheet.cell(1, i).value == col_name:
            return i
    return -1


def find_sid_index_in_sheet(worksheet, sid):
    for i in range(1, worksheet.max_row + 1):
        if worksheet.cell(i, 1).value == sid:
            return i
    return -1


def grade_students(worksheet, test_case_name, grade, sid_list, version=0):
    col = find_col_index_in_sheet(worksheet, test_case_name)
    if col == -1:
        raise Exception("Test case does not exist!!")
    row = find_sid_index_in_sheet(worksheet, sid_list[0])
    if grade == grade.OK:
        if worksheet.cell(row, col).value == 0:
            worksheet.cell(row, col).value = FULL_TESTCASE_GRADE - loss_rate * version


def save_result(worksheet, grade, sid_list, test_case_name=None, version=0):
    if test_case_name is not None:
        test_case_name = test_case_name.split(testcase_extension)[0]
    row = find_sid_index_in_sheet(worksheet, sid_list[0])
    col = find_col_index_in_sheet(worksheet, COMPILED)
    if grade != Grade.ERROR:
        worksheet.cell(row, col).value = "Yes"
    else:
        return
    grade_students(worksheet, test_case_name, grade, sid_list, version)


def build_project():
    if pom_file not in os.listdir(os.getcwd()):
        raise Exception("the directory you are in does not contain a maven project")
    print("############## building project ##############")
    compile_command = "mvn install -Dmaven.test.skip=true"
    p = subprocess.Popen(compile_command, shell=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.wait()
    out, err = p.communicate()
    if out is not None and FAILURE in str(out):
        print("############## code has compile error ##############")
        return False
    print("############## building done successfully ##############\n")
    return True


def evaluate(testcase_root, testcase_name, output, pure_stderr):
    try:
        with open(os.path.join(testcase_root, testcase_name.split(testcase_extension)[0] + output_extension),
                  "r") as text_file:  # HYPO: file exists
            expected = text_file.read().replace("\r\n", "").replace("\n", "").replace("\t", "").replace(" ", "")

        text_file.close()
    except OSError as e:
        expected = output
    if testcase_name.startswith(fail_prefix) and pure_stderr is not None and len(pure_stderr) > 0:
        print("TEST CASE PASSED!\n")
        return True
    elif expected != output:
        print("TEST CASE FAILED!!!!!: ")
        print("EXPECTED:", expected)
        print("OUTPUT:", output)
        print("\n\n")
        return False
    else:
        print("TEST CASE PASSED!\n")
        return True


def decompress(code_root, compressed_code_name):
    prev_path = cur_dir
    os.chdir(code_root)
    os.mkdir(temp_directory)
    copyfile(os.path.join(code_root, compressed_code_name), os.path.join(temp_directory, compressed_code_name))
    zip_ref = zipfile.ZipFile(os.path.join(code_root, compressed_code_name), 'r')
    zip_ref.extractall(os.path.join(code_root, temp_directory))
    zip_ref.close()
    os.remove(os.path.join(temp_directory, compressed_code_name))
    os.chdir(prev_path)
    return os.path.join(code_root, temp_directory)


def copy_files(cur_dir, files_to_copy):
    for (root, dirs, files) in os.walk(cur_dir):
        for file in files:
            if file in files_to_copy:
                copyfile(os.path.join(root, file), os.path.join(files_to_copy.get(file), file))


def extract_and_copy_goals(code_root, compressed_code_name, files_to_copy):
    try:
        decompressed_code_location = decompress(code_root, compressed_code_name)
    except OSError:
        rmtree(os.path.join(code_root, temp_directory))
        os.chdir(cur_dir)
        raise Exception('this file name does not exist on code repo')
    copy_files(decompressed_code_location, files_to_copy)
    rmtree(os.path.join(code_root, decompressed_code_location))


def execute_project(testcase_root, testcase_name):
    runner = runner_class
    run_command = "mvn -q exec:java -Dexec.mainClass=" + runner + " -Dexec.args=" + os.path.join(
        testcase_root, testcase_name)
    p = subprocess.Popen(run_command, shell=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.wait()
    out, err = p.communicate()
    output = str(out)[2: len(str(out)) - 1].replace("\\r\\n", "").replace("\\n", "").replace("\\t",
                                                                                             "").replace(" ", "")
    pure_output = output
    pure_stderr = str(err)[2: len(str(err)) - 1]
    return pure_output, pure_stderr


def clean_project_artifact():
    print("############ cleaning project #############")
    prev_path = os.getcwd()
    os.chdir(project_dir)
    clean_command = "mvn clean"
    p = subprocess.Popen(clean_command, shell=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.wait()
    os.chdir(prev_path)
    print("############ end of cleaning project #############")


def begin_examination(sid_list, worksheet, version):
    prev_path = os.getcwd()
    os.chdir(project_dir)
    print("--------------------------------- group ", ','.join(sid_list), "-------------------------------------")
    compiled = build_project()
    if not compiled:
        save_result(worksheet, Grade.ERROR, sid_list)
    else:
        for (testcase_root, testcase_dirs, testcase_files) in os.walk(testcases_folder):
            for testcase_name in testcase_files:
                if testcase_name.endswith(testcase_extension):
                    print("############## running code with test case", testcase_name,
                          "is started  ##############\n")
                    pure_output, pure_stderr = execute_project(testcase_root, testcase_name, )
                    grade = Grade.FAULT
                    if evaluate(testcase_root, testcase_name, pure_output, pure_stderr):
                        grade = Grade.OK
                    save_result(worksheet, grade, sid_list, testcase_name, version)
    print("------------------------------------------------------------------------------------------------------\n\n")
    os.chdir(prev_path)


def get_sids(code_name):
    sid = code_name.split(compressed_code_extension)[0]
    return sid.split(separator)


def remove_copied_files(files_to_copy):
    for (root, dirs, files) in os.walk(project_dir):
        for file in files:
            if file in files_to_copy:
                os.remove(os.path.join(root, file))


def save_new_code_to(files_to_copy, dir, new_code_name):
    prev_path = os.getcwd()
    os.chdir(dir)
    zip_file = zipfile.ZipFile(new_code_name, 'w')
    for file in files_to_copy:
        zip_file.write(os.path.join(files_to_copy.get(file), file), compress_type=zipfile.ZIP_DEFLATED)
    os.chdir(prev_path)


def get_num_of_runs_for_std(sids, worksheet):
    row = find_sid_index_in_sheet(worksheet, sids[0])
    col = find_col_index_in_sheet(worksheet, RUNSNUM)
    if row == -1:
        worksheet.append(create_new_student(worksheet, sids))
        row = worksheet.max_row
    version = worksheet.cell(row, col).value
    return version


def prepare_project(code_root, code_name, version, copy_from_source=True):
    _version = version
    if _version >= max_run_num:
        raise Exception("max number of runs exceeded")
    new_code_name = ('' if _version is 0 else (newer_version_sign + str(_version) + '_')) + code_name
    if not (new_code_name in os.listdir(code_root) or (not copy_from_source)):
        raise Exception("version " + str(_version) + " of this code does not exist on repo")
    if copy_from_source:
        extract_and_copy_goals(code_root, new_code_name, files_to_copy)


def examinate_group(worksheet, sids, version):
    begin_examination(sids, worksheet, version)
    clean_project_artifact()


def do_examination_scenario(code_root, code_name, version, copy_from_source=True):
    sids = get_sids(code_name)
    std_row = find_sid_index_in_sheet(worksheet, sids[0])
    run_col = find_col_index_in_sheet(worksheet, RUNSNUM)
    if std_row == -1:
        create_new_student(worksheet, sids)
    prepare_project(code_root, code_name, version, copy_from_source)
    if not copy_from_source:
        saved_code_name = code_name if version == 0 else newer_version_sign + str(version) + '_' + code_name
        save_new_code_to(files_to_copy, code_root, saved_code_name)
    examinate_group(worksheet, sids, version)
    remove_copied_files(files_to_copy)
    worksheet.cell(std_row, run_col).value = worksheet.cell(std_row, run_col).value + 1


def examinate_all(worksheet, version=None):
    recent_students = set({})
    code_dir = codes_folder
    for (code_root, codeDirs, code_files) in os.walk(code_dir):
        for code_name in code_files:
            if code_name.endswith(compressed_code_extension) and not code_name.startswith(newer_version_sign):
                sids = get_sids(code_name)
                if len(set(sids) & recent_students) is 0:
                    recent_students |= set(sids)
                    try:
                        if version is None:
                            version = get_num_of_runs_for_std(sids, worksheet)
                        do_examination_scenario(code_root, code_name, version)
                    except Exception as exception:
                        print(exception)


def try_test(code_root, code_name, version, copy_from_source, test_id):
    testcase_root = ""
    testcase_name = ""
    try:
        tests_csv_file = pandas.read_csv(testcase_mapper_filename)
        testcase_position = list(tests_csv_file['id']).index(test_id)
        testcase_root = tests_csv_file['testcase_dir'][testcase_position]
        testcase_name = tests_csv_file['testcase_name'][testcase_position]
    except Exception as exception:
        print('there is a problem in tests')
        exit(1)

    prepare_project(code_root, code_name, version, copy_from_source)
    prev_path = os.getcwd()
    os.chdir(project_dir)
    compiled = build_project()
    if compiled:
        pure_output, pure_stderr = execute_project(testcase_root, testcase_name + testcase_extension)
        print('OUTPUT OF YOUR TEST IS', pure_output)
        print('STDERR OF YOUR TEST IS', pure_stderr)
        clean_project_artifact()
    if copy_from_source:
        remove_copied_files(files_to_copy)
    os.chdir(prev_path)


def find_sid_code_name(sids):
    for (code_root, codeDirs, code_files) in os.walk(codes_folder):
        for code_name in code_files:
            filename_list = [separator.join(list(element)) + compressed_code_extension for element in
                             list(itertools.permutations(sids))]
            for filename in filename_list:
                if code_name == filename:
                    return code_root, code_name
    return None, None


def create_default_row():
    row1 = [('sid' + str(i + 1)) for i in range(NUMOFSTUDENTS)]
    row1.extend([COMPILED, RUNSNUM])
    row2 = ["810199XXX" for i in range(NUMOFSTUDENTS)]
    row2.extend(["No", 0])
    for (testcase_root, testcase_dirs, testcase_files) in os.walk(testcases_folder):
        for testcase_name in testcase_files:
            if testcase_name.endswith(testcase_extension):
                testCase = testcase_name.split(testcase_extension)[0]
                row1.append(testCase)
                row2.append(0)
    return [row1, row2]


def create_excel(excel_name):
    try:
        workbook = openpyxl.load_workbook(excel_name)
        worksheet = workbook.active
    except:
        number_tests()
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = excel_name.split(excel_extension)[0]
        header_rows = create_default_row()
        worksheet.append(header_rows[0])
        worksheet.append(header_rows[1])
    return worksheet, workbook


def parse_run_command(command, worksheet, excel_name):
    if '-single' in command:
        print("enter sids : ")
        sids = input().split()
        if len(sids) <= 0:
            print("you must enter at least one sid")
            return
        copy_from_source = False
        if '-noCopyFromSource' not in command:
            copy_from_source = True
        group_code_folder, code_name = find_sid_code_name(sids)
        if group_code_folder is None or code_name is None:
            print('no code with such student-ids')
            return
        sids = get_sids(code_name)
        try:
            version = get_num_of_runs_for_std(sids, worksheet)
            if '-try' in command:
                print("enter test id :")
                test_id = int(input())
                try_test(group_code_folder, code_name, version - 1, copy_from_source, test_id)
            else:
                do_examination_scenario(group_code_folder, code_name, version, copy_from_source)
        except Exception as exception:
            print(exception)
    else:
        examinate_all(worksheet)
    workbook.save(excel_name)


def is_there_any_change_in_testcases_dir(testcase_mapper_columns):
    if testcase_mapper_filename in os.listdir(cur_dir):
        cur_testcases_name = set({})
        tests_csv_file = pandas.read_csv(testcase_mapper_filename)
        if set(testcase_mapper_columns) == set(tests_csv_file.columns):
            for (root, dirs, files) in os.walk(testcases_folder):
                for test_file in files:
                    if test_file.endswith(testcase_extension):
                        cur_testcases_name.add(test_file)
            csv_tests_name = set(
                {testcase_name + testcase_extension for testcase_name in tests_csv_file['testcase_name']})
            if cur_testcases_name == csv_tests_name:
                return False
    return True


def number_tests():
    test_id = 0
    testcase_mapper = {'id': [], 'testcase_dir': [], 'testcase_name': []}
    change_detected = is_there_any_change_in_testcases_dir({'id', 'testcase_dir', 'testcase_name'})
    if change_detected:
        for (test_dir, test_dirs, test_files) in os.walk(testcases_folder):
            for test_file in test_files:
                if test_file.endswith(testcase_extension):
                    test_id += 1
                    testcase_name = test_file.split(testcase_extension)[0]
                    new_testcase_name = testcase_name + '_' + str(test_id)
                    os.rename(os.path.join(test_dir, test_file),
                              os.path.join(test_dir, new_testcase_name + testcase_extension))
                    if not testcase_name.startswith(fail_prefix):
                        output_name = testcase_name + output_extension
                        new_output_name = new_testcase_name + output_extension
                        os.rename(os.path.join(test_dir, output_name), os.path.join(test_dir, new_output_name))
                    testcase_mapper.get('id').append(test_id)
                    testcase_mapper.get('testcase_dir').append(test_dir)
                    testcase_mapper.get('testcase_name').append(new_testcase_name)
        dataframe = DataFrame(testcase_mapper, columns=['id', 'testcase_dir', 'testcase_name'])
        dataframe.to_csv(testcase_mapper_filename, index=None, header=True)


def correct_testcases_file_structure_and_format():
    test_id = 0
    try:
        for (test_root, test_dirs, test_files) in os.walk(testcases_folder):
            for test_file in test_files:
                if test_file.endswith(testcase_extension):
                    test_id += 1
                    testcase_name = test_file.split(testcase_extension)[0]
                    if not testcase_name.startswith(fail_prefix):
                        if testcase_name + output_extension not in os.listdir(test_root):
                            raise Exception(
                                'test file with name ' + test_file + ' must be passed but its output is missing')
                        if not testcase_name.startswith(pass_prefix):
                            new_test_name = pass_prefix + testcase_name
                            new_output_file_name = new_test_name + output_extension
                            os.rename(os.path.join(test_root, test_file),
                                      os.path.join(test_root, new_test_name + testcase_extension))
                            os.rename(os.path.join(test_root, testcase_name + output_extension),
                                      os.path.join(test_root, new_output_file_name))
    except Exception as exception:
        print(exception)
        exit(1)


def list_testcases(prefix=None):
    testcases = pandas.read_csv(testcase_mapper_filename, header=0)
    print(DataFrame(
        [testcase for testcase in testcases['testcase_name'] if prefix is None or testcase.startswith(prefix)],
        columns=['testcase_name']))


def parse_list_testcases(command):
    if '-fail' in command:
        list_testcases(fail_prefix)
    elif '-pass' in command:
        list_testcases(pass_prefix)
    else:
        list_testcases()


def remove_duplicate_codes():
    recent_students = set({})
    code_dir = codes_folder
    for (code_root, codeDirs, code_files) in os.walk(code_dir):
        for code_name in code_files:
            if code_name.endswith(compressed_code_extension) and not code_name.startswith(newer_version_sign):
                sids = get_sids(code_name)
                if len(set(sids) & recent_students) is 0:
                    recent_students |= set(sids)
                else:
                    os.remove(os.path.join(code_root, code_name))


def list_groups():
    group_id = 0
    code_dir = codes_folder
    for (code_root, codeDirs, code_files) in os.walk(code_dir):
        for code_name in code_files:
            if code_name.endswith(compressed_code_extension) and not code_name.startswith(newer_version_sign):
                group_id += 1
                sids = get_sids(code_name)
                print('group', group_id, ':', ' , '.join(sids))


if __name__ == "__main__":
    correct_testcases_file_structure_and_format()
    remove_duplicate_codes()
    excel_name = "Grades"
    excel_file_name = excel_name + excel_extension
    worksheet, workbook = create_excel(excel_file_name)
    workbook.save(excel_file_name)
    help = "run( or r as shorthand command ): runs tests for all codes located in codes folder which is hard coded \n\t " \
           + "option single : runs tests for one code, it runs the test on the living code coming with -noCopyFromSource" \
           + " and if it comes with -try it just runs a test after getting its id" \
           + "\nhelp( h ) : prints this manual\n" \
           + "exit: termination of cli\n" \
           + "list_tests: lists all tests available in test case folder with name, if it comes with" \
             " -fail , it only lists testcases which lead to failure and if it comes with -pass" \
             "it only lists testcases that must be passed\n\n" \
           + "list_groups: list all gropus who sent you code\n\n"
    while True:
        print('>>>>>', end=" ")
        command = str(input())
        if command == 'exit':
            print("######### bye , see you soon! #########")
            break
        elif command.startswith('run') or command.startswith('r'):
            parse_run_command(command, worksheet, excel_file_name)
        elif command == 'help' or command == 'h':
            print(help)
        elif command.startswith('list_tests'):
            parse_list_testcases(command)
        elif command.startswith('list_groups'):
            list_groups()
        else:
            print("unknown command")
            print(help)
