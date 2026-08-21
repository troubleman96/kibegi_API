package search

import (
	"context"
	"database/sql"
	"errors"
	"time"
)

type History struct {
	ID          int64     `json:"id"`
	Query       string    `json:"query"`
	ResultCount int       `json:"result_count"`
	Categories  any       `json:"categories_searched"`
	CreatedAt   time.Time `json:"created_at"`
}
type Repository struct{ DB *sql.DB }

func (r Repository) Search(ctx context.Context, userID int64, query string, limit int, categories []string) (map[string]any, error) {
	if r.DB == nil {
		return nil, errors.New("database is not configured")
	}
	allowed := map[string]bool{"users": true, "classes": true, "files": true, "friends": true, "library": true}
	selected := categories
	if len(selected) == 0 {
		selected = []string{"users", "classes", "files", "friends", "library"}
	}
	results := map[string]any{}
	counts := map[string]int{}
	total := 0
	for _, cat := range selected {
		if !allowed[cat] {
			continue
		}
		var rows *sql.Rows
		var err error
		switch cat {
		case "users":
			rows, err = r.DB.QueryContext(ctx, `SELECT id,email,full_name,user_type,NULLIF(profile_image,'') FROM authentication_user WHERE is_active=true AND id<>$1 AND (email ILIKE $2 OR full_name ILIKE $2) ORDER BY full_name LIMIT $3`, userID, "%"+query+"%", limit)
		case "classes":
			rows, err = r.DB.QueryContext(ctx, `SELECT id,class_code,name,description FROM classes_class WHERE name ILIKE $1 OR class_code ILIKE $1 ORDER BY name LIMIT $2`, `%`+query+`%`, limit)
		case "files":
			rows, err = r.DB.QueryContext(ctx, `SELECT u.id,u.file_code,u.file_name,u.file_type,u.description FROM uploads_upload u WHERE u.is_deleted=false AND (u.file_name ILIKE $1 OR u.description ILIKE $1) AND (u.uploader_id=$2 OR EXISTS(SELECT 1 FROM classes_membership m WHERE m.class_obj_id=u.class_obj_id AND m.user_id=$2)) ORDER BY u.created_at DESC LIMIT $3`, `%`+query+`%`, userID, limit)
		case "library":
			rows, err = r.DB.QueryContext(ctx, `SELECT i.id,i.item_code,i.title,i.file_type,i.subject,i.is_featured,i.view_count,i.download_count FROM library_libraryitem i WHERE i.status='public' AND (i.title ILIKE $1 OR i.description ILIKE $1 OR i.subject ILIKE $1) ORDER BY i.is_featured DESC,i.created_at DESC LIMIT $2`, `%`+query+`%`, limit)
		case "friends":
			rows, err = r.DB.QueryContext(ctx, `SELECT u.id,u.email,u.full_name,u.user_type FROM authentication_user u WHERE u.id<>$1 AND EXISTS(SELECT 1 FROM friends_friendship f WHERE f.status='accepted' AND ((f.user_id=$1 AND f.friend_id=u.id) OR (f.friend_id=$1 AND f.user_id=u.id))) AND (u.email ILIKE $2 OR u.full_name ILIKE $2) LIMIT $3`, userID, "%"+query+"%", limit)
		}
		if err != nil {
			return nil, err
		}
		items := make([]map[string]any, 0)
		for rows.Next() {
			item := map[string]any{"type": cat}
			var scanErr error
			switch cat {
			case "users", "friends":
				var id int64
				var email, name, typ string
				var image sql.NullString
				scanErr = rows.Scan(&id, &email, &name, &typ, &image)
				item["id"] = id
				item["email"] = email
				item["full_name"] = name
				item["user_type"] = typ
			case "classes":
				var id string
				var code, name, desc string
				scanErr = rows.Scan(&id, &code, &name, &desc)
				item["id"] = id
				item["class_code"] = code
				item["name"] = name
				item["description"] = desc
			case "files":
				var id, code, name, typ, desc string
				scanErr = rows.Scan(&id, &code, &name, &typ, &desc)
				item["id"] = id
				item["file_code"] = code
				item["file_name"] = name
				item["file_type"] = typ
				item["description"] = desc
			case "library":
				var id, code, title, typ, subject string
				var featured bool
				var views, downloads int
				scanErr = rows.Scan(&id, &code, &title, &typ, &subject, &featured, &views, &downloads)
				item["id"] = id
				item["item_code"] = code
				item["title"] = title
				item["file_type"] = typ
				item["subject"] = subject
				item["is_featured"] = featured
				item["view_count"] = views
				item["download_count"] = downloads
			}
			if scanErr != nil {
				rows.Close()
				return nil, scanErr
			}
			items = append(items, item)
		}
		rows.Close()
		results[cat] = items
		counts[cat] = len(items)
		total += len(items)
	}
	_, _ = r.DB.ExecContext(ctx, `INSERT INTO search_searchhistory (query,result_count,categories_searched,created_at,user_id) VALUES ($1,$2,$3,NOW(),$4)`, query, total, selected, userID)
	return map[string]any{"query": query, "total_results": total, "results": results, "counts": counts}, nil
}
func (r Repository) Suggestions(ctx context.Context, query string, limit int) ([]map[string]any, error) {
	rows, err := r.DB.QueryContext(ctx, `SELECT 'user' AS type,full_name AS label,email AS detail FROM authentication_user WHERE is_active=true AND (full_name ILIKE $1 OR email ILIKE $1) UNION ALL SELECT 'class',name,class_code FROM classes_class WHERE name ILIKE $1 UNION ALL SELECT 'library',title,subject FROM library_libraryitem WHERE status='public' AND title ILIKE $1 LIMIT $2`, "%"+query+"%", limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]map[string]any, 0)
	for rows.Next() {
		var typ, label, detail string
		if err := rows.Scan(&typ, &label, &detail); err != nil {
			return nil, err
		}
		out = append(out, map[string]any{"type": typ, "label": label, "detail": detail})
	}
	return out, rows.Err()
}
func (r Repository) History(ctx context.Context, userID int64) ([]History, error) {
	rows, err := r.DB.QueryContext(ctx, `SELECT id,query,result_count,categories_searched,created_at FROM search_searchhistory WHERE user_id=$1 ORDER BY created_at DESC LIMIT 20`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]History, 0)
	for rows.Next() {
		var x History
		if err := rows.Scan(&x.ID, &x.Query, &x.ResultCount, &x.Categories, &x.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, x)
	}
	return out, rows.Err()
}
func (r Repository) ClearHistory(ctx context.Context, userID int64) error {
	_, err := r.DB.ExecContext(ctx, `DELETE FROM search_searchhistory WHERE user_id=$1`, userID)
	return err
}
