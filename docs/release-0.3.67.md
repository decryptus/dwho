# DWho 0.3.67

Existing CBC writes through `DWhoCryptoHelper.encrypt` and `serialize` now
emit a Python `DeprecationWarning`. Both methods still produce the historical
wire format. Legacy readers continue to read existing records.

For a gradual migration, track the record format explicitly and deploy readers
for both versions first. Read CBC records only from a trusted source. Write
new byte strings with `encrypt_authenticated` and JSON-compatible values with
`serialize_authenticated`. Convert other Python types explicitly. Verify that
the new record decrypts to the expected value before replacing the old one.
Treat a failed EAX authentication check as an error.

The [encryption and migration guide](../README.md#encryption-and-migration)
describes key lengths, legacy pickle handling and the EAX format.
