import argparse
import csv

def symmetrize_matrix(data):
    """Symmetrize the given matrix stored as a list of lists."""
    n = len(data)
    for i in range(n):
        for j in range(n):
            data[i][j] = min(data[i][j], data[j][i])
    return data

def read_matrix(file_name, has_header):
    """Read a TSV file into a list of lists, handling optional headers."""
    with open(file_name, 'r', newline='',encoding="utf-8") as file:
        reader = csv.reader(file, delimiter='\t')
        if has_header:
            header = next(reader)            
        else:
            header = None
        
        # Read data into a list of lists, converting values to integers
        matrix = []
        for row in reader:
            if has_header:
                row = row[1:]
            matrix.append([int(x) for x in row])
    print(header)
    print(matrix[0][0])
    return header, matrix

def write_matrix(file_name, matrix, header=None):
    """Write the symmetrized matrix to a TSV file, handling optional headers."""
    with open(file_name, 'w', newline='',encoding="utf8") as file:
        writer = csv.writer(file, delimiter='\t')
        if header:
            writer.writerow(header)
            for i in range(1,len(header)):
                matrix[i-1] = [header[i]]+matrix[i-1]
        for row in matrix:
            writer.writerow(row)

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Symmetrize a distance matrix from a TSV file.')
    parser.add_argument('input_file', type=str, help='Input TSV file name')
    parser.add_argument('-d', '--header', action='store_true', help='Indicate if the TSV contains headers')
    parser.add_argument('-o', '--output', type=str, help='Output TSV file name (optional)')

    # Parse arguments
    args = parser.parse_args()
    
    # Read the matrix from the file
    header, matrix = read_matrix(args.input_file, args.header)
    
    # Symmetrize the matrix
    symmetrized_matrix = symmetrize_matrix(matrix)
    
    # Write the symmetrized matrix to the file
    output_file = args.output if args.output else args.input_file
    write_matrix(output_file, symmetrized_matrix, header=header if args.header else None)

if __name__ == '__main__':
    main()
