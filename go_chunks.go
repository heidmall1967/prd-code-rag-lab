package main

import (
	"encoding/json"
	"go/ast"
	"go/parser"
	"go/token"
	"log"
	"os"
	"path/filepath"
	"strings"
)

func main() {
	if len(os.Args) < 2 {
		log.Fatal("usage: go_chunks FILE.go ...")
	}

	output := json.NewEncoder(os.Stdout)
	for _, path := range os.Args[1:] {
		source, err := os.ReadFile(path)
		if err != nil {
			log.Fatal(err)
		}
		positions := token.NewFileSet()
		file, err := parser.ParseFile(positions, path, source, 0)
		if err != nil {
			log.Fatal(err)
		}
		relative, err := filepath.Rel("data/scorecard", path)
		if err != nil {
			log.Fatal(err)
		}

		kind := "code"
		if strings.HasSuffix(path, "_test.go") {
			kind = "test"
		}
		emit := func(symbol string, node ast.Node) {
			start := positions.Position(node.Pos())
			end := positions.Position(node.End())
			row := map[string]any{
				"symbol":     file.Name.Name + "." + symbol,
				"body":       string(source[start.Offset:end.Offset]),
				"path":       filepath.ToSlash(relative),
				"start_line": start.Line,
				"end_line":   end.Line,
				"kind":       kind,
			}
			if err := output.Encode(row); err != nil {
				log.Fatal(err)
			}
		}

		for _, item := range file.Decls {
			switch declaration := item.(type) {
			case *ast.FuncDecl:
				emit(declaration.Name.Name, declaration)

			case *ast.GenDecl:
				if declaration.Tok != token.CONST {
					continue
				}
				for _, part := range declaration.Specs {
					value, ok := part.(*ast.ValueSpec)
					if !ok {
						continue
					}
					for _, name := range value.Names {
						emit(name.Name, value)
					}
				}
			}
		}
	}
}
