from dotenv import load_dotenv
load_dotenv() # before other imports so os.getenv will include .env values
import uuid
import jsonpatch
import pymongo
import os
from bson.json_util import dumps, loads
from flask import abort, Blueprint, jsonify, request, current_app
from datetime import datetime, timezone
from ..swagger import validate
from pymongo import MongoClient

user = os.getenv("DB_USER")
secret = os.getenv("DB_PASS")
uri_path = os.getenv("URI_PATH")
app_name = __name__.split(".")[-1]
app = Blueprint(app_name, app_name)
cluster = MongoClient(f"mongodb+srv://{user}:{secret}@{uri_path}")
db = cluster["UndocuGuide"]
collection = db["Scholarships"]


todos = [] # this example just updates this array, probably should update a database


def find(f, seq):
  """Return first item in sequence where f(item) == True"""
  for item in seq:
    if f(item): 
      return item


@app.route('/api/v1/scholarships')
def list_scholarships():
  """ List all scholarship entries
  ---
  tags:
    - Scholarships

  definitions:
    Scholarship:
      type: object
      properties:
        id: { type: string }
        name: { type: string }
        due: { type: string, format: date-time }
        state: { type: string}
        completed: { type: string, format: date-time }
        last_updated: { type: string, format: date-time }
      required: [ id, note, created ]

  responses:
    200:
      content:
        application/json:
          schema:
            type: array
            items:
              $ref: '#/definitions/Scholarship'
  """
  cursor = collection.find().limit(10)
  list_cur = list(cursor)
  result = dumps(list_cur)

  return current_app.response_class(result, mimetype="application/json")


@app.route('/api/v1/scholarship/<id>')
def get_entry(id):
  """ Get a scholarship entry
  ---
  tags:
    - Scholarships
  parameters:
    - name: id
      in: path
      schema: { type: string }
  responses:
    404:
      description: Not Found
    200:
      content:
        application/json:
          schema:
            type: object
            properties:
              note: { type: string }
              due: { type: string, format: date-time }
              done: { type: boolean }
              created: { type: string, format: date-time }
              completed: { type: string, format: date-time }
              last_update: { type: string, format: date-time }
  """
  entry = find(lambda x: x['id'] == id, todos)
  if entry is None:
    abort(404, 'Entry Not Found')
  return jsonify(entry)


@app.route('/api/v1/scholarship', methods=['POST'])
def create():
  """ Create a new scholarship entry
  ---
  tags:
    - Scholarships
  requestBody:
    required: true
    content:
      application/json:
        schema:
          $ref: '#/definitions/CreateTodo'

  definitions:
    CreateTodo:
      type: object
      properties:
        note: { type: string }
        due: { type: string, format: date-time }
      required: [ note ]

  responses:
    400:
      description: Bad Request
    201:
      content:
        application/json:
          schema:
            $ref: '#/definitions/Scholarship'
  """
  json = request.get_json()
  #validate(json, 'CreateTodo')
  #json['id'] = str(uuid.uuid4())
  #json['created'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
  #todos.append(json)
  collection.insert_one(json)
  return json


@app.route('/api/v1/scholarship/<id>', methods=['PUT'])
def update(id):
  """ Update or create a scholarship entry
  ---
  tags:
    - Scholarships
  parameters:
    - name: id
      in: path
      schema: { type: string }
  requestBody:
    required: true
    content:
      application/json:
        schema:
          $ref: '#/definitions/Scholarship'

  responses:
    400:
      description: Bad Request
    200:
      content:
        application/json:
          schema:
            $ref: '#/defintions/Scholarship'
  """
  json = request.get_json()
  validate(json, 'Todo')

  json['id'] = id # reject any id changes
  json['last_updated'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

  entry = find(lambda x: x['id'] == id, todos)
  if entry is not None:
    todos.remove(entry)
  todos.append(json)

  return jsonify(json)


@app.route('/api/v1/scholarship/<id>', methods=['PATCH'])
def patch(id):
  """ Update a scholarship entry
  ---
  tags:
    - Scholarships
  parameters:
    - name: id
      in: path
      schema: { type: string }
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: array
          items:
            oneOf:
              - type: object
                properties:
                  op: { type: string, enum: ['add', 'replace', 'test'] }
                  path: { type: string }
                  value: { }
                required: [ op, path, value ]
              - type: object
                properties:
                  op: { type: string, enum: ['remove', 'replace'] }
                  path: { type: string }
                required: [ op, path ]
              - type: object
                properties:
                  op: { type: string, enum: ['move', 'copy'] }
                  from: { type: string }
                  path: { type: string }
                required: [ op, from, path ]
          example:
            - op: replace
              path: /note
              value: updated note

  responses:
    400:
      description: Bad Request
    404:
      description: Not Found
    422:
      description: Invalid Patch Result
    201:
      description: Test Failed; Patch Not Applied
    200:
      content:
        application/json:
          schema:
            $ref: '#/definitions/Scholarship'

  """
  json = request.get_json()

  entry = find(lambda x: x['id'] == id, todos)
  if entry is None:
    abort(404, 'Entry Not Found')

  try:
    patch = jsonpatch.JsonPatch(json)
    result = patch.apply(entry)
  except jsonpatch.InvalidJsonPatch as e:
    abort(400, str(e))
  except jsonpatch.JsonPatchConflict as e:
    abort(409, str(e))
  except jsonpatch.JsonPatchTestFailed as e:
    return jsonify(entry), 201

  result['id'] = id # reject any id changes
  result['last_updated'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
  validate(result, 'Todo', 422)
  todos.remove(entry)
  todos.append(result)
  return jsonify(result)


@app.route('/api/v1/scholarship/<id>', methods=['DELETE'])
def delete(id):
  """ Remove a scholarship entry
  ---
  tags:
    - Scholarships
  parameters:
    - name: id
      in: path
      schema: { type: string }
  responses:
    204:
      description: Already Removed
    200:
      description: Successfully Removed
      content:
        application/json:
          schema:
            $ref: '#/definitions/Scholarship'
  """
  entry = find(lambda x: x['id'] == id, todos)
  if entry is None:
    return '', 204
  todos.remove(entry)

  return jsonify(entry)